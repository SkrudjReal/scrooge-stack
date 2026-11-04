#!/usr/bin/env python3
"""Merge Scrooge instructions, preserving other global instructions."""
from datetime import datetime
from pathlib import Path
import shutil
import sys

BEGIN = '<!-- scrooge-stack:begin -->'
END = '<!-- scrooge-stack:end -->'


def merge(source: Path, destination: Path) -> bool:
    old = destination.read_text(encoding='utf-8') if destination.exists() else ''
    if old.count(BEGIN) != old.count(END) or old.count(BEGIN) > 1:
        raise ValueError(f'invalid managed markers in {destination}')
    block = BEGIN + '\n' + source.read_text(encoding='utf-8').rstrip() + '\n' + END
    if BEGIN in old:
        start, end = old.index(BEGIN), old.index(END) + len(END)
        if end < start:
            raise ValueError(f'invalid marker order in {destination}')
        new = old[:start] + block + old[end:]
    else:
        new = old + ('\n' if old and not old.endswith('\n') else '') + ('\n' if old else '') + block + '\n'
    if old == new:
        return False
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        backup = destination.with_name(destination.name + '.bak.' + datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
        shutil.copy2(destination, backup)
        print(f'Backup: {backup}')
    destination.write_text(new, encoding='utf-8')
    print(f'Updated: {destination}')
    return True


if __name__ == '__main__':
    try:
        merge(Path(sys.argv[1]), Path(sys.argv[2]))
    except (OSError, ValueError, IndexError, UnicodeError) as exc:
        sys.exit(f'Cannot merge instructions: {exc}')
