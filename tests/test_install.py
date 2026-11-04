import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / 'home'
        self.home.mkdir()
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.mock('git', '''#!/usr/bin/env python3
import os, pathlib, sys
if sys.argv[1:2] == ['-C']:
 print((pathlib.Path(sys.argv[2])/'.mock-origin').read_text()); sys.exit(0)
if os.environ.get('TEST_FAIL_URL') and any(os.environ['TEST_FAIL_URL'] in arg for arg in sys.argv): sys.exit(1)
p=pathlib.Path(sys.argv[-1]); (p/'.git').mkdir(parents=True)
(p/'.mock-origin').write_text(sys.argv[-2])
if 'ponytail' in str(p) or 'agentic-awesome-skills' in str(p):
 q=p/'skills'/'example'; q.mkdir(parents=True); (q/'SKILL.md').write_text('---\\nname: example\\ndescription: auto activate\\n---\\nBody\\n')
''')
        self.mock('graphify', '''#!/usr/bin/env python3
import os, pathlib
p=pathlib.Path(os.environ['HOME'])/'.codex/skills/graphify'; p.mkdir(parents=True)
(p/'SKILL.md').write_text('---\\nname: graphify\\ndescription: auto activate\\n---\\nBody\\n')
''')
        self.mock('zsh', '#!/bin/sh\nexit 0\n')
        self.mock('agy', '#!/bin/sh\nprintf "deploychan  http\\nxerj  stdio\\n"\n')
        self.mock('shellcheck', '#!/bin/sh\nexit 0\n')
        self.env = dict(os.environ, HOME=str(self.home), XDG_DATA_HOME=str(self.home / '.local/share'), PATH=str(self.bin) + os.pathsep + os.environ['PATH'])
        self.env.pop('CODEX_HOME', None)
        self.env.pop('ZSH_CUSTOM', None)

    def mock(self, name, content):
        path = self.bin / name
        path.write_text(content)
        path.chmod(0o755)

    def run_installer(self, *args, env=None, xerj=False):
        skip = ['--skip-obsidian'] + ([] if xerj else ['--skip-xerj'])
        return subprocess.run(['bash', str(ROOT / 'install.sh'), '--targets', 'agy', *skip, *args], env=env or self.env, cwd=self.root, text=True, capture_output=True)

    def test_dry_run_does_not_mutate_home_and_reports_order(self):
        result = self.run_installer('--dry-run')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(list(self.home.iterdir()), [])
        offsets = [result.stdout.index(f'{i}/10 ') for i in range(1, 11)]
        self.assertEqual(offsets, sorted(offsets))

    def test_codex_dry_run_never_invokes_codex(self):
        self.mock('codex', '#!/bin/sh\ntouch "$HOME/was-invoked"\n')
        result = subprocess.run(['bash', str(ROOT / 'install.sh'), '--targets', 'codex', '--skip-xerj', '--skip-zsh', '--dry-run'], env=self.env, cwd=self.root, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(list(self.home.iterdir()), [])

    def test_obsidian_flags_reach_shared_helper_and_failure_stops(self):
        self.mock('python3', '#!' + sys.executable + '''
import json, os, pathlib, sys
if len(sys.argv) > 1 and pathlib.Path(sys.argv[1]).name == 'install-obsidian.py':
 (pathlib.Path(os.environ['HOME'])/'obsidian-args.json').write_text(json.dumps(sys.argv[2:]))
 sys.exit(int(os.environ.get('TEST_OBSIDIAN_EXIT', '0')))
os.execv(sys.executable, [sys.executable, *sys.argv[1:]])
''')
        cmd = ['bash', str(ROOT / 'install.sh'), '--targets', 'agy', '--skip-xerj', '--skip-zsh',
               '--obsidian-vault', '/test/Vault with spaces', '--obsidian-repo', '/test/Repo with spaces', '--obsidian-write']
        result = subprocess.run(cmd, env=self.env, cwd=self.root, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        args = json.loads((self.home / 'obsidian-args.json').read_text())
        self.assertEqual(args[args.index('--vault') + 1], '/test/Vault with spaces')
        self.assertEqual(args[args.index('--repo') + 1], '/test/Repo with spaces')
        self.assertIn('--enable-writes', args)
        failed = subprocess.run(cmd, env=dict(self.env, TEST_OBSIDIAN_EXIT='7'), cwd=self.root, text=True, capture_output=True)
        self.assertNotEqual(failed.returncode, 0)
        self.assertNotIn('9/10 Global instructions', failed.stdout)
        self.assertNotIn('10/10 Choirboy', failed.stdout)

    def test_install_and_reinstall_preserve_configuration(self):
        config = self.home / '.gemini/config/mcp_config.json'
        config.parent.mkdir(parents=True)
        config.write_text(json.dumps({'other': {'keep': 42}, 'mcpServers': {'other': {'command': 'other'}}}))
        prompt = self.home / '.gemini/GEMINI.md'
        prompt.write_text('My own instructions\n')
        existing_skill = self.home / '.gemini/config/skills/example/SKILL.md'
        existing_skill.parent.mkdir(parents=True)
        existing_skill.write_text('My existing skill\n')
        rc = self.home / '.zshrc'
        rc.write_text('export PATH="$HOME/bin:$PATH"\nplugins=(git)\nsource "$ZSH/oh-my-zsh.sh"\n')
        first = self.run_installer()
        self.assertEqual(first.returncode, 0, first.stderr)
        updated = json.loads(config.read_text())
        self.assertEqual(updated['mcpServers']['other']['command'], 'other')
        self.assertEqual(updated['other']['keep'], 42)
        self.assertTrue(list(config.parent.glob('mcp_config.json.bak.*')))
        self.assertIn('My own instructions', prompt.read_text())
        self.assertEqual(existing_skill.read_text(), 'My existing skill\n')
        self.assertIn('export PATH="$HOME/bin:$PATH"', rc.read_text())
        snapshots = [p.read_text() for p in (config, prompt, rc)]
        second = self.run_installer()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual([p.read_text() for p in (config, prompt, rc)], snapshots)
        self.assertIn('Use only when the user explicitly requests', (self.home / '.gemini/config/skills/graphify/SKILL.md').read_text())

    def test_failure_stops_before_choirboy(self):
        env = dict(self.env, TEST_FAIL_URL='agentic-awesome-skills')
        result = self.run_installer('--skip-zsh', env=env)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('10/10 Choirboy', result.stdout)

    def test_conflicting_mcp_is_preserved(self):
        config = self.home / '.gemini/config/mcp_config.json'
        config.parent.mkdir(parents=True)
        original = '{"mcpServers":{"deploychan":{"serverUrl":"https://other.invalid"}}}'
        config.write_text(original)
        result = self.run_installer('--skip-zsh')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(config.read_text(), original)
        self.assertNotIn('10/10 Choirboy', result.stdout)

    def test_xerj_checksum_mismatch_stops_install(self):
        self.mock('curl', '''#!/usr/bin/env python3
import pathlib,sys
p=pathlib.Path(sys.argv[sys.argv.index('-o')+1])
p.write_text('0'*64 if str(p).endswith('.sha256') else 'not a release')
''')
        result = self.run_installer('--skip-zsh', xerj=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('SHA-256 verification failed', result.stderr)
        self.assertFalse((self.home / '.local/bin/xerj').exists())
        self.assertNotIn('10/10 Choirboy', result.stdout)

    def test_invalid_mcp_json_stops_install(self):
        config = self.home / '.gemini/config/mcp_config.json'
        config.parent.mkdir(parents=True)
        config.write_text('{broken')
        result = self.run_installer('--skip-zsh')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(config.read_text(), '{broken')
        self.assertNotIn('10/10 Choirboy', result.stdout)

    def test_unavailable_download_stops_install(self):
        self.mock('curl', '#!/bin/sh\nexit 22\n')
        result = self.run_installer('--skip-zsh', xerj=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('10/10 Choirboy', result.stdout)

    def test_shellcheck_install_dry_run_and_reinstall(self):
        (self.bin / 'shellcheck').unlink()
        system_bin = self.root / 'system-bin'
        system_bin.mkdir()
        for path in Path('/usr/bin').iterdir():
            if path.name != 'shellcheck':
                (system_bin / path.name).symlink_to(path)
        self.mock('id', '#!/bin/sh\nprintf "1000\\n"\n')
        self.mock('sudo', '#!/bin/sh\nexec "$@"\n')
        self.mock('apt-get', '''#!/bin/sh
printf '%s\\n' "$*" >> "$HOME/apt-calls"
printf '#!/bin/sh\\nexit 0\\n' > "$SCROOGE_TEST_BIN/shellcheck"
chmod +x "$SCROOGE_TEST_BIN/shellcheck"
''')
        env = dict(self.env, PATH=str(self.bin) + os.pathsep + str(system_bin), SCROOGE_TEST_BIN=str(self.bin))
        dry = self.run_installer('--skip-zsh', '--dry-run', env=env)
        self.assertEqual(dry.returncode, 0, dry.stderr)
        self.assertIn('sudo apt-get install -y shellcheck', dry.stdout)
        self.assertFalse((self.home / 'apt-calls').exists())
        first = self.run_installer('--skip-zsh', env=env)
        self.assertEqual(first.returncode, 0, first.stderr)
        second = self.run_installer('--skip-zsh', env=env)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual((self.home / 'apt-calls').read_text().splitlines(), ['install -y shellcheck'])
        self.assertFalse((self.home / '.local/bin/xerj').exists())

    def test_missing_target_cli_stops_before_changes(self):
        (self.bin / 'agy').unlink()
        env = dict(self.env, PATH=str(self.bin) + ':/usr/bin:/bin')
        result = self.run_installer('--skip-zsh', env=env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Missing prerequisite: agy', result.stderr)
        self.assertEqual(list(self.home.iterdir()), [])

    def test_xerj_wrappers_require_key_and_bind_loopback(self):
        binary = self.home / '.local/bin/xerj'
        binary.parent.mkdir(parents=True)
        binary.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$HOME/xerj-args"\n')
        binary.chmod(0o755)
        mcp = subprocess.run(['bash', str(ROOT / 'scripts/xerj-mcp.sh')], env=self.env, capture_output=True, text=True)
        self.assertNotEqual(mcp.returncode, 0)
        self.assertFalse((self.home / 'xerj-args').exists())
        key = self.home / '.local/share/scrooge-stack/xerj-data/admin.key'
        key.parent.mkdir(parents=True)
        key.write_text('test-key')
        self.mock('cat', '#!/bin/sh\nexit 1\n')
        mcp = subprocess.run(['bash', str(ROOT / 'scripts/xerj-mcp.sh')], env=self.env, capture_output=True, text=True)
        self.assertNotEqual(mcp.returncode, 0)
        self.assertFalse((self.home / 'xerj-args').exists())
        start = subprocess.run(['bash', str(ROOT / 'scripts/xerj-start.sh')], env=self.env, capture_output=True, text=True)
        self.assertEqual(start.returncode, 0, start.stderr)
        args = (self.home / 'xerj-args').read_text().splitlines()
        self.assertIn('/dev/null', args)
        self.assertIn('127.0.0.1', args)
        self.assertNotIn('--insecure', args)


if __name__ == '__main__':
    unittest.main()
