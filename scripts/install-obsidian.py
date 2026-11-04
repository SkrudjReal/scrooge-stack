#!/usr/bin/env python3
"""Shared native Windows/Linux Obsidian bootstrap. Python 3.11+, no global pip."""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import tomllib

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = 'https://github.com/howdeploy/ObsidianDataWeave.git'
REVISION = 'ddc40c68941d66943824c668ed192aced866fce8'
MCP_VERSION = '0.18.3'
READ_TOOLS = ('read_note', 'list_directory', 'search_notes', 'read_multiple_notes',
              'get_notes_info', 'get_frontmatter', 'get_vault_stats', 'list_all_tags',
              'wiki_link', 'get_note_outline', 'read_note_lines')
SKILL_NAME = 'obsidian-dataweave-codex'


def run(*args, **kwargs):
    # Windows Python pipes otherwise use the local code page, breaking Cyrillic/FTS snippets.
    kwargs['env'] = dict(kwargs.get('env', os.environ), PYTHONUTF8='1', PYTHONIOENCODING='utf-8')
    return subprocess.run([str(x) for x in args], check=True, **kwargs)


def save(path: Path, text: str):
    """Back up before changing existing files; replace atomically, preserve mode."""
    content = text.encode('utf-8')
    if path.exists() and path.read_bytes().decode('utf-8-sig') == text:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o600
    if path.exists():
        shutil.copy2(path, str(path) + '.bak.' + datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as f:
        pending = Path(f.name)
        f.write(content)
    try:
        pending.chmod(mode)
        os.replace(pending, path)
    finally:
        pending.unlink(missing_ok=True)


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else {}
    if not isinstance(value, dict):
        raise ValueError(f'Expected JSON object: {path}')
    return value


def discover_vault(explicit: str | None, home: Path, codex_home: Path) -> Path | None:
    def valid(path):
        return path.is_dir() and (path / '.obsidian').is_dir()

    if explicit:
        path = Path(explicit).expanduser().resolve()
        if not valid(path):
            raise ValueError(f'Not an existing Obsidian vault (.obsidian missing): {path}')
        return path
    # Prefer the vault already configured for Codex; never invent a new one.
    config = codex_home / 'config.toml'
    if config.exists():
        data = tomllib.loads(config.read_text(encoding='utf-8-sig'))
        for arg in data.get('mcp_servers', {}).get('mcpvault', {}).get('args', []):
            if isinstance(arg, str) and valid(Path(arg)):
                return Path(arg).resolve()
    registries = [home / '.config/obsidian/obsidian.json',
                  Path(os.environ.get('APPDATA', home / 'AppData/Roaming')) / 'obsidian/obsidian.json']
    profiles = Path('/mnt/c/Users')
    if sys.platform != 'win32' and profiles.is_dir():
        registries += list(profiles.glob('*/AppData/Roaming/obsidian/obsidian.json'))
    candidates = set()
    for registry in registries:
        if not registry.exists():
            continue
        for info in load_json(registry).get('vaults', {}).values():
            raw = info.get('path', '')
            if not raw:
                continue
            if sys.platform != 'win32' and re.match(r'^[A-Za-z]:[\\/]', raw):
                raw = '/mnt/' + raw[0].lower() + '/' + raw[3:].replace('\\', '/')
            path = Path(raw)
            if valid(path):
                candidates.add(path.resolve())
    roots = [home / 'Documents', home / 'OneDrive/Documents', home]
    if sys.platform != 'win32' and profiles.is_dir():
        roots += list(profiles.glob('*/Documents'))
    for parent in roots:
        if parent.is_dir():
            for marker in parent.glob('*/.obsidian'):
                if marker.is_dir():
                    candidates.add(marker.parent.resolve())
    if len(candidates) > 1:
        raise ValueError('Multiple vaults found; choose --obsidian-vault / -ObsidianVault:\n' +
                         '\n'.join(str(p) for p in sorted(candidates)))
    return next(iter(candidates), None)


def compatible(entry: dict, vault: Path) -> bool:
    args = entry.get('args', [])
    if not isinstance(args, list) or len(args) not in (2, 3):
        return False
    if not all(isinstance(x, str) for x in args):
        return False
    return (isinstance(entry.get('command'), str) and
            args[0].replace('\\', '/').endswith('/@bitbonsai/mcpvault/dist/server.js') and
            Path(args[1]).resolve() == vault.resolve() and
            (len(args) == 2 or args[2] == '--read-only'))


def replace_args(text: str, args: list[str]) -> str:
    """Replace just one TOML value, retaining comments, other tables and keys."""
    table = re.search(r'^\[mcp_servers\.mcpvault\][^\n]*\n(?P<body>.*?)(?=^\[|\Z)', text, re.M | re.S)
    if not table:
        raise ValueError('Nonstandard mcpvault TOML table: change its args manually')
    match = re.search(r'^args\s*=.*(?:\n|$)', table['body'], re.M)
    if not match:
        raise ValueError('mcpvault args missing')
    start = table.start('body') + match.start()
    end = table.start('body') + match.end()
    while True:
        try:
            tomllib.loads(text[start:end])
            break
        except tomllib.TOMLDecodeError:
            newline = text.find('\n', end)
            if end >= table.end('body') or newline < 0:
                raise ValueError('Cannot safely replace mcpvault args') from None
            end = newline + 1
    return text[:start] + 'args = ' + json.dumps(args, ensure_ascii=True) + '\n' + text[end:]


def plan_configs(home: Path, codex_home: Path, targets: list[str], vault: Path,
                 node: str, server: Path, enable_writes: bool) -> list[tuple[Path, str, bool]]:
    plans = []
    for target in targets:
        path = (codex_home / 'config.toml' if target == 'codex' else home /
                ('.gemini/config/mcp_config.json' if target == 'agy' else '.gemini/settings.json'))
        old = path.read_bytes().decode('utf-8-sig') if path.exists() else ''
        data = tomllib.loads(old) if target == 'codex' else load_json(path)
        key = 'mcp_servers' if target == 'codex' else 'mcpServers'
        servers = data.get(key, {})
        if not isinstance(servers, dict):
            raise ValueError(f'{key} must be an object: {path}')
        entry = servers.get('mcpvault')
        if entry is not None and (not isinstance(entry, dict) or not compatible(entry, vault)):
            raise ValueError(f'Conflicting mcpvault in {path}; existing configuration preserved')
        transition = enable_writes and (entry is None or '--read-only' in entry['args'])
        if entry is not None:
            if not transition:
                plans.append((path, old, False))
                continue
            args = [a for a in entry['args'] if a != '--read-only']
            if target == 'codex':
                new = replace_args(old, args)
                check = tomllib.loads(new)
                expected = tomllib.loads(old)
                expected[key]['mcpvault']['args'] = args
                if check != expected:
                    raise ValueError('TOML change would affect unrelated configuration')
            else:
                entry['args'] = args
                new = json.dumps(data, indent=2, ensure_ascii=False) + '\n'
        else:
            args = [str(server), str(vault)] + ([] if enable_writes else ['--read-only'])
            if target == 'codex':
                new = old + ('\n' if old and not old.endswith('\n') else '')
                new += '\n[mcp_servers.mcpvault]\ncommand = ' + json.dumps(node) + '\n'
                new += 'args = ' + json.dumps(args) + '\nstartup_timeout_sec = 30\n'
                new += 'default_tools_approval_mode = "writes"\n'
                for tool in READ_TOOLS:
                    new += f'\n[mcp_servers.mcpvault.tools.{tool}]\napproval_mode = "approve"\n'
                tomllib.loads(new)
            else:
                data.setdefault(key, {})['mcpvault'] = {'command': node, 'args': args}
                new = json.dumps(data, indent=2, ensure_ascii=False) + '\n'
        plans.append((path, new, transition))
    return plans


def backup_vault(vault: Path, data_dir: Path) -> Path:
    parent = data_dir / 'backups'
    parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    destination = parent / ('vault-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    destination.mkdir(mode=0o700)
    excluded = ('.smart-env', '.git', '.trash')
    shutil.copytree(vault, destination, symlinks=True, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns(*excluded))
    hashes = {}
    for base, dirs, files in os.walk(vault):
        dirs[:] = [d for d in dirs if d not in excluded and not (Path(base) / d).is_symlink()]
        for name in files:
            source = Path(base) / name
            if source.is_symlink():
                continue
            rel = source.relative_to(vault)
            def digest(path):
                with path.open('rb') as f:
                    return hashlib.file_digest(f, 'sha256').hexdigest()
            hashes[str(rel)] = digest(source)
            if hashes[str(rel)] != digest(destination / rel):
                raise ValueError('Vault changed during backup; writes remain disabled')
    save(destination.with_suffix('.manifest.json'), json.dumps(
        {'vault': str(vault), 'excluded': excluded, 'symlinks': 'preserved, not followed',
         'sha256': hashes}, indent=2, ensure_ascii=False) + '\n')
    print(f'[obsidian] Backup verified: {destination} ({len(hashes)} files; caches/trash excluded)')
    return destination


class MCP:
    """Small stdio probe using a reader thread so Windows pipes also work."""
    def __init__(self, node: str, server: Path, vault: Path, readonly: bool):
        self.err = tempfile.TemporaryFile()
        self.p = subprocess.Popen([node, str(server), str(vault)] + (['--read-only'] if readonly else []),
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.err)
        self.responses = queue.Queue()
        self.seq = 0
        def read():
            for line in self.p.stdout:
                try:
                    self.responses.put(json.loads(line))
                except ValueError:
                    self.responses.put({'error': 'Invalid MCP JSON'})
            self.responses.put({'error': 'MCP exited'})
        self.reader = threading.Thread(target=read, daemon=True)
        self.reader.start()

    def request(self, method, params=None):
        self.seq += 1
        self.p.stdin.write((json.dumps({'jsonrpc': '2.0', 'id': self.seq, 'method': method,
                                       'params': params or {}}) + '\n').encode())
        self.p.stdin.flush()
        while True:
            value = self.responses.get(timeout=30)
            if value.get('id') == self.seq or 'error' in value:
                return value

    def initialize(self):
        result = self.request('initialize', {'protocolVersion': '2025-03-26', 'capabilities': {},
                                            'clientInfo': {'name': 'scrooge-probe', 'version': '1'}})
        if 'error' in result:
            raise ValueError('MCP initialization failed')
        self.p.stdin.write(b'{"jsonrpc":"2.0","method":"notifications/initialized"}\n')
        self.p.stdin.flush()

    def tool(self, name, **args):
        return self.request('tools/call', {'name': name, 'arguments': args})

    def close(self):
        self.p.stdin.close()
        try:
            self.p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.p.kill()
            self.p.wait(timeout=5)
        self.reader.join(timeout=5)
        self.p.stdout.close()
        self.err.close()


def verify_mcp(node: str, server: Path):
    with tempfile.TemporaryDirectory(prefix='scrooge-obsidian-mcp-') as temp:
        vault = Path(temp) / 'vault'
        vault.mkdir()
        outside = Path(temp) / 'outside.md'
        outside.write_text('outside sentinel', encoding='utf-8')
        (vault / 'Seed.md').write_text('# Seed\nlexical quartz\n', encoding='utf-8')
        for readonly in (True, False):
            client = MCP(node, server, vault, readonly)
            try:
                client.initialize()
                tools = {t['name'] for t in client.request('tools/list')['result']['tools']}
                assert 'read_note' in tools
                assert ('write_note' in tools) != readonly
                result = client.tool('write_note', path='Test.md', content='quartz [[Seed]]',
                                     frontmatter={'custom': 'keep', 'tags': ['test']})
                if readonly:
                    assert 'error' in result or result.get('result', {}).get('isError')
                    assert not (vault / 'Test.md').exists()
                else:
                    assert not result['result'].get('isError'), result
                    result = client.tool('patch_note', path='Test.md', oldString='quartz', newString='opal')
                    assert not result['result'].get('isError'), result
                    result = client.tool('read_note', path='Test.md')
                    note = json.loads(result['result']['content'][0]['text'])
                    assert note['fm']['custom'] == 'keep' and 'opal [[Seed]]' in note['content']
                result = client.tool('read_note', path='../outside.md')
                assert 'error' in result or result.get('result', {}).get('isError')
                result = client.tool('write_note', path='../outside.md', content='must not escape')
                assert 'error' in result or result.get('result', {}).get('isError')
                assert outside.read_text(encoding='utf-8') == 'outside sentinel'
            finally:
                client.close()
    print('[obsidian] MCP read-only/write/frontmatter/wiki-link/path probes passed (temporary vault)')


def configure_dataweave(repo: Path, vault: Path, data_dir: Path):
    path = repo / 'config.toml'
    if path.exists():
        cfg = tomllib.loads(path.read_text(encoding='utf-8-sig'))
        if Path(cfg.get('vault', {}).get('vault_path', '')).resolve() != vault:
            raise ValueError(f'DataWeave uses a different vault: {path}')
        if not cfg.get('memory', {}).get('enabled', True):
            raise ValueError('Existing DataWeave FTS5 is disabled; enable it explicitly')
        return
    text = (repo / 'config.example.toml').read_text(encoding='utf-8')
    text = text.replace('"/path/to/your/obsidian/vault"', json.dumps(vault.as_posix()))
    text = text.replace('"/tmp/dw/staging"', json.dumps((data_dir / 'staging').as_posix()))
    text = text.replace('db_dir = ""', 'db_dir = ' + json.dumps((data_dir / 'index').as_posix()))
    tomllib.loads(text)
    save(path, text)


def verify_dataweave(repo: Path, python: Path):
    with tempfile.TemporaryDirectory(prefix='scrooge-dataweave-') as temp:
        base = Path(temp)
        copy = base / 'dataweave'
        shutil.copytree(repo, copy, ignore=shutil.ignore_patterns(
            '.git', '.venv', '__pycache__', '.pytest_cache', 'config.toml', 'processed.json'))
        vault = base / 'vault'
        vault.mkdir()
        configure_dataweave(copy, vault, base)
        def script(name, *args):
            try:
                result = run(python, copy / 'scripts' / name, *args, cwd=copy,
                             capture_output=True, text=True, encoding='utf-8', timeout=60)
            except subprocess.CalledProcessError as exc:
                raise ValueError(f'Temporary {name} probe failed:\n{exc.stderr}\n{exc.stdout}') from None
            return result.stdout + result.stderr
        (vault / 'Seed.md').write_text('# Seed\nquartz\n', encoding='utf-8')
        script('memory_index.py', 'build')
        assert 'Seed.md' in script('memory_index.py', 'search', 'quartz', '--json')
        (vault / 'Seed.md').write_text('# Seed\nquartz opal\n', encoding='utf-8')
        script('memory_index.py', 'update')
        assert 'Seed.md' in script('memory_index.py', 'search', 'opal', '--json')
        nested = vault / 'Nested/Deep/Knowledge.md'
        nested.parent.mkdir(parents=True)
        nested.write_text('# Knowledge\nportablequartz\n', encoding='utf-8')
        script('memory_index.py', 'update')
        assert 'Nested/Deep/Knowledge.md' in script('memory_index.py', 'search', 'portablequartz', '--folder', 'Nested', '--json')
        plan = {'notes': [
            {'id': 'a', 'title': 'Atomic', 'note_type': 'atomic', 'tags': ['tech/ai', 'productivity/pkm'],
             'date': '2026-01-01', 'source_doc': 'probe.md', 'body': 'One idea. [[Map]]'},
            {'id': 'm', 'title': 'Map', 'note_type': 'moc', 'tags': ['tech/ai', 'productivity/pkm'],
             'date': '2026-01-01', 'source_doc': 'probe.md', 'body': '- [[Atomic]]'}]}
        source = base / 'plan.json'
        source.write_text(json.dumps(plan), encoding='utf-8')
        for _ in range(2):
            script('process.py', str(source), '--from-plan', '--non-interactive', '--on-conflict', 'skip')
        assert (vault / 'Guides & Overviews/Map.md').read_text(encoding='utf-8').count('[[Atomic]]') == 1
        plan['notes'][1]['body'] += '\n- [[Seed]]'
        source.write_text(json.dumps(plan), encoding='utf-8')
        script('process.py', str(source), '--from-plan', '--non-interactive', '--on-conflict', 'skip')
        moc = (vault / 'Guides & Overviews/Map.md').read_text(encoding='utf-8')
        assert '[[Seed]]' in moc and moc.count('[[Atomic]]') == 1
        atomic = vault / 'Research & Insights/Atomic.md'
        assert '[[Map]]' in atomic.read_text(encoding='utf-8')
        shutil.copy2(atomic, atomic.with_name('Atomic copy.md'))
        assert 'Atomic copy' in script('dedup_vault.py', '--dry-run', '--skip-claude')
        script('wiki_init.py', 'demo', '--mode', 'project', '--title', 'Demo')
        script('wiki_ingest.py', 'demo', str(vault / 'Seed.md'), '--kind', 'docs', '--no-compile')
        script('wiki_compile.py', 'demo', '--regenerate-index-only', '--on-conflict', 'overwrite')
        script('wiki_lint.py', 'demo', '--strict')
    print('[obsidian] Native FTS5/atomic-plan/MOC/replay/dedup/Wiki probes passed (no LLM/auth)')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vault')
    parser.add_argument('--targets', default='codex')
    parser.add_argument('--data-dir', type=Path, required=True)
    parser.add_argument('--repo', type=Path)
    parser.add_argument('--enable-writes', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args(argv)
    targets = args.targets.split(',')
    if not targets or any(t not in ('codex', 'agy', 'gemini') for t in targets):
        parser.error('Invalid targets')
    home = Path.home()
    codex_home = Path(os.environ.get('CODEX_HOME', home / '.codex')).expanduser().resolve()
    vault = discover_vault(args.vault, home, codex_home)
    if vault is None:
        print('[obsidian] No existing vault found; no vault created. Rerun with --obsidian-vault / -ObsidianVault.')
        return
    data_dir = args.data_dir.expanduser().resolve()
    repo = (args.repo or home / 'projects/mainstream/ObsidianDataWeave').expanduser().resolve()
    # Refuse runtime/backup paths inside the vault before any filesystem changes.
    if (data_dir.is_relative_to(vault) or repo.is_relative_to(vault) or
            vault.is_relative_to(repo) or data_dir.is_relative_to(repo)):
        raise ValueError('Runtime/repository/backup paths must stay outside the vault')
    node = shutil.which('node')
    if not node:
        raise ValueError('Install Node.js >=22.12 with npm first')
    node = str(Path(node).resolve())
    server = data_dir / 'npm/node_modules/@bitbonsai/mcpvault/dist/server.js'
    plans = plan_configs(home, codex_home, targets, vault, node, server, args.enable_writes)
    if (repo / 'config.toml').exists():
        configure_dataweave(repo, vault, data_dir)  # Validate existing config without replacing it.
    print(f'[obsidian] Existing vault: {vault}; DataWeave: {repo}')
    if args.dry_run:
        print('[dry-run] Would install pinned MCPVault/DataWeave, test temporary vaults, build FTS5 and register skills/MCP.')
        if any(p[2] for p in plans):
            print('[dry-run] Would hash-verify a vault backup before enabling writes.')
        return
    version = run(node, '--version', capture_output=True, text=True).stdout.strip().lstrip('v')
    if tuple(int(x) for x in version.split('.')[:3]) < (22, 12, 0):
        raise ValueError('MCPVault needs Node >=22.12')
    npm = shutil.which('npm')
    npm_paths = ([Path(npm).resolve()] if npm else []) + [Path(node).parent / 'node_modules/npm/bin/npm-cli.js']
    if npm:
        npm_paths.append(Path(npm).parent / 'node_modules/npm/bin/npm-cli.js')
    npm_cli = next((p for p in npm_paths if p.suffix == '.js' and p.is_file()), None)
    if npm_cli is None:
        raise ValueError('Cannot locate npm-cli.js; install npm alongside Node (no cmd.exe wrapper used)')
    if repo.exists():
        origin = run('git', '-C', repo, 'remote', 'get-url', 'origin', capture_output=True, text=True).stdout.strip()
        if origin.removesuffix('.git') != UPSTREAM.removesuffix('.git'):
            raise ValueError(f'Unexpected DataWeave origin: {repo}; preserving it')
    else:
        repo.parent.mkdir(parents=True, exist_ok=True)
        run('git', 'clone', '-c', 'core.autocrlf=false', UPSTREAM, repo)
        run('git', '-C', repo, 'checkout', '--detach', REVISION)
    for filename in ('dataweave.patch', 'dataweave-portable-paths.patch', 'dataweave-windows-yaml.patch'):
        patch = ROOT / 'obsidian' / filename
        if not run_patch_check(repo, patch, reverse=True):
            if not run_patch_check(repo, patch):
                raise ValueError(f'DataWeave {filename} conflicts; review checkout manually')
            run('git', '-C', repo, 'apply', '--ignore-space-change', patch)
    for test in ('test_atom_plan_prompt.py', 'test_vault_scan_pruning.py', 'test_portable_paths.py'):
        path = repo / 'tests' / test
        content = (ROOT / 'obsidian' / test).read_text(encoding='utf-8')
        if path.exists() and path.read_text(encoding='utf-8') != content:
            raise ValueError(f'Existing regression test differs: {path}')
        save(path, content)
    python = repo / '.venv' / ('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')
    if not python.exists():
        run(sys.executable, '-m', 'venv', repo / '.venv')
    run(python, '-m', 'pip', 'install', '-r', repo / 'requirements.txt')
    configure_dataweave(repo, vault, data_dir)
    # Use the official Codex install mode on Linux; native Windows has no Bash requirement.
    if sys.platform != 'win32':
        env = dict(os.environ, PATH=str(python.parent) + os.pathsep + os.environ.get('PATH', ''))
        run('bash', repo / 'install.sh', '--mode', 'codex' if 'codex' in targets else 'local',
            '--vault-path', vault, cwd=repo, env=env)
    run(node, npm_cli, 'install', '--prefix', data_dir / 'npm', '--save-exact',
        f'@bitbonsai/mcpvault@{MCP_VERSION}')
    verify_mcp(node, server)
    verify_dataweave(repo, python)
    run(python, repo / 'scripts/memory_index.py', 'build', cwd=repo)
    template = (ROOT / 'obsidian/SKILL.md').read_text(encoding='utf-8')
    skill = template.replace('@@REPO@@', str(repo)).replace('@@VAULT@@', str(vault)).replace('@@PYTHON@@', str(python))
    for target in targets:
        directory = (codex_home / 'skills' if target == 'codex' else home /
                     ('.gemini/config/skills' if target == 'agy' else '.gemini/skills'))
        path = directory / SKILL_NAME / 'SKILL.md'
        if path.exists() and '<!-- scrooge-obsidian -->' not in path.read_text(encoding='utf-8'):
            raise ValueError(f'Existing user skill preserved: {path}; review it or use --skip-obsidian')
        save(path, skill)
    if any(p[2] for p in plans):
        backup_vault(vault, data_dir)
    # Recheck optimistic config snapshots after potentially slow downloads/backup.
    current = plan_configs(home, codex_home, targets, vault, node, server, args.enable_writes)
    if current != plans:
        raise ValueError('Agent config changed during installation; no MCP config written, retry')
    for path, text, _ in plans:
        save(path, text)
    prompts = set()
    if 'codex' in targets:
        prompts.add(codex_home / 'AGENTS.md')
    if 'agy' in targets or 'gemini' in targets:
        prompts.add(home / '.gemini/GEMINI.md')
    for path in sorted(prompts):
        run(sys.executable, ROOT / 'scripts/merge-prompt.py', ROOT / 'obsidian/AGENTS.md',
            path, '--block-name', 'scrooge-obsidian')
    save(data_dir / 'installation.json', json.dumps({'vault': str(vault), 'repo': str(repo),
         'mcpvault': MCP_VERSION, 'dataweave_base': REVISION, 'targets': targets}, indent=2) + '\n')
    print('[obsidian] Verified and configured. Restart selected agents; preview/approve destructive operations.')


def run_patch_check(repo, patch, reverse=False):
    args = ['git', '-C', str(repo), 'apply', '--ignore-space-change', '--check']
    if reverse:
        args.append('--reverse')
    return subprocess.run(args + [str(patch)], capture_output=True).returncode == 0


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, AssertionError, queue.Empty, subprocess.SubprocessError) as exc:
        sys.exit(f'Obsidian setup failed: {exc}. Existing notes/configurations were not replaced blindly.')
