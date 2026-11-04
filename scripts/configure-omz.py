#!/usr/bin/env python3
"""Update the three supported Oh My Zsh settings without replacing the rc file."""
import argparse
from datetime import datetime
from pathlib import Path
import re
import shutil


SETTINGS = (
    (r'^[ \t]*ZSH_THEME[ \t]*=[^\n]*$', 'ZSH_THEME="robbyrussell"'),
    (r'^[ \t]*plugins[ \t]*=[ \t]*\([^)]*\)[ \t]*(?:\#[^\n]*)?$', 'plugins=(git zsh-autosuggestions zsh-syntax-highlighting)'),
    (r'''^[ \t]*zstyle[ \t]+['"]?:omz:update['"]?[ \t]+mode[ \t]+[^\n]*$''', "zstyle ':omz:update' mode auto"),
)


def configure(path: Path, dry_run: bool = False) -> bool:
    exists = path.exists()
    original = path.read_text(encoding='utf-8') if exists else ''
    base = original if exists else 'export ZSH="$HOME/.oh-my-zsh"\nsource "$ZSH/oh-my-zsh.sh"\n'
    source_pattern = r'^[ \t]*(?:source|\.)[ \t]+[^\n]*oh-my-zsh\.sh[^\n]*$'
    original_sources = list(re.finditer(source_pattern, base, re.MULTILINE))
    if len(original_sources) != 1:
        raise ValueError('expected exactly one Oh My Zsh source line; configure it manually')
    updated = base
    missing = []
    for pattern, value in SETTINGS:
        regex = re.compile(pattern, re.MULTILINE)
        matches = list(regex.finditer(updated))
        if len(matches) > 1:
            raise ValueError(f'multiple assignments for {value.split("=")[0]}; resolve manually')
        if matches:
            if matches[0].start() > re.search(source_pattern, updated, re.MULTILINE).start():
                raise ValueError('setting after Oh My Zsh source; move it before the source line')
            updated = regex.sub(lambda _: value, updated, count=1)
        else:
            missing.append(value)
    # Unrecognized multiline or dynamic plugin configuration must not be shadowed.
    if re.search(r'^[ \t]*plugins[ \t]*=', original, re.MULTILINE) and not re.search(SETTINGS[1][0], original, re.MULTILINE):
        raise ValueError('unsupported plugins assignment; update it manually')
    source = re.search(source_pattern, updated, re.MULTILINE)
    if missing:
        if not source:
            raise ValueError('Oh My Zsh source line not found; add it manually before configuring')
        updated = updated[:source.start()] + '\n'.join(missing) + '\n' + updated[source.start():]
    if updated == original:
        return False
    if dry_run:
        print(f'[dry-run] Would update {path}')
        return True
    if path.exists():
        backup = path.with_name(path.name + '.bak.' + datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
        shutil.copy2(path, backup)
        print(f'Backup: {backup}')
    path.write_text(updated, encoding='utf-8')
    return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--file', type=Path, default=Path.home() / '.zshrc')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    try:
        print('Updated' if configure(args.file, args.dry_run) else 'Unchanged')
    except (OSError, UnicodeError, ValueError) as exc:
        parser.exit(1, f'Cannot configure Oh My Zsh: {exc}\n')
