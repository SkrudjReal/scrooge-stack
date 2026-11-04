#!/usr/bin/env python3
"""Merge Scrooge instructions, preserving other global instructions."""
from datetime import datetime
import argparse
from pathlib import Path
import re
import shutil
import sys

def merge(source: Path, destination: Path, block_name: str = 'scrooge-stack') -> bool:
    if not re.fullmatch(r'[a-z0-9-]+', block_name):
        raise ValueError('Invalid prompt block name')
    begin, finish = f'<!-- {block_name}:begin -->', f'<!-- {block_name}:end -->'
    old = destination.read_bytes().decode('utf-8') if destination.exists() else ''
    if old.count(begin) != old.count(finish) or old.count(begin) > 1:
        raise ValueError(f'invalid managed markers in {destination}')
    block = begin + '\n' + source.read_text(encoding='utf-8-sig').rstrip() + '\n' + finish
    if begin in old:
        start, end = old.index(begin), old.index(finish) + len(finish)
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
    destination.write_bytes(new.encode('utf-8'))
    print(f'Updated: {destination}')
    return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('destination', type=Path)
    parser.add_argument('--block-name', default='scrooge-stack')
    args = parser.parse_args()
    try:
        merge(args.source, args.destination, args.block_name)
    except (OSError, ValueError, IndexError, UnicodeError) as exc:
        sys.exit(f'Cannot merge instructions: {exc}')
