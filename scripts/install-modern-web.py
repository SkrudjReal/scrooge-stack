#!/usr/bin/env python3
"""Install Google's Modern Web Guidance skill on Linux/WSL or native Windows."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

UPSTREAM = 'https://github.com/GoogleChrome/modern-web-guidance.git'
SKILL = 'modern-web-guidance'


def destinations(home, targets):
    roots = {
        'codex': Path(os.environ.get('CODEX_HOME') or home / '.codex'),
        'agy': home / '.gemini/config',
        'gemini': home / '.gemini',
    }
    return [roots[target].expanduser() / 'skills' / SKILL for target in targets]


def checkout(repo):
    if (repo / '.git').exists():
        origin = subprocess.run(['git', '-C', str(repo), 'remote', 'get-url', 'origin'],
                                check=True, capture_output=True, text=True).stdout.strip()
        if origin.removesuffix('.git') != UPSTREAM.removesuffix('.git'):
            raise ValueError(f'Unexpected Git origin; preserving {repo}')
    else:
        if os.path.lexists(repo):
            raise ValueError(f'Refusing to replace existing path: {repo}')
        repo.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(['git', 'clone', '--depth', '1', UPSTREAM, str(repo)], check=True)
    source = repo / 'skills' / SKILL
    if not (source / 'SKILL.md').is_file() or not (source / 'guides').is_dir() or not (repo / 'LICENSE').is_file():
        raise ValueError(f'Incomplete Modern Web Guidance checkout: {repo}')
    return source


def install_skill(source, destination):
    if os.path.lexists(destination):
        print(f'[modern-web] Preserved existing skill: {destination}')
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Stage the complete skill so an interrupted copy cannot become a skipped partial install.
    with tempfile.TemporaryDirectory(prefix='.modern-web-', dir=destination.parent) as temp:
        staged = Path(temp) / SKILL
        shutil.copytree(source, staged)
        shutil.copy2(source.parents[1] / 'LICENSE', staged / 'LICENSE')
        staged.rename(destination)
    print(f'[modern-web] Installed: {destination}')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--targets', default='codex,agy,gemini')
    parser.add_argument('--data-dir', type=Path)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args(argv)
    targets = args.targets.split(',')
    if any(target not in ('codex', 'agy', 'gemini') for target in targets):
        parser.error('Invalid targets; use codex,agy,gemini')
    home = Path.home()
    if args.data_dir is None:
        base = Path(os.environ['LOCALAPPDATA']) if os.name == 'nt' else Path(os.environ.get('XDG_DATA_HOME') or home / '.local/share')
        args.data_dir = base / 'scrooge-stack'
    repo = args.data_dir.expanduser() / 'sources' / SKILL
    paths = destinations(home, targets)
    if args.dry_run:
        print(f'[dry-run] Would verify Node.js 22+/npm/npx and clone or reuse {UPSTREAM} at {repo}')
        for path in paths:
            print(f'[dry-run] Would install {path} (preserve existing skills)')
        return
    node = shutil.which('node')
    if not node or not shutil.which('npm') or not shutil.which('npx'):
        raise ValueError('Modern Web Guidance requires Node.js 22+ with npm/npx')
    version = subprocess.run([node, '--version'], check=True, capture_output=True, text=True).stdout.strip()
    if int(version.lstrip('v').split('.')[0]) < 22:
        raise ValueError('Modern Web Guidance requires Node.js 22+')
    source = checkout(repo)
    for path in paths:
        install_skill(source, path)
    print('[modern-web] Restart selected agents; verify with npx -y modern-web-guidance@latest search "light dismiss dialog"')


if __name__ == '__main__':
    main()
