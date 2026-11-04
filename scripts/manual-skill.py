#!/usr/bin/env python3
"""Restrict automatic skill discovery to an explicit invocation."""
from pathlib import Path
import re
import sys

path = Path(sys.argv[1])
name = sys.argv[2]
text = path.read_text(encoding='utf-8')
parts = text.split('---', 2)
if len(parts) != 3 or parts[0].strip():
    sys.exit(f'Invalid skill frontmatter: {path}')
front, count = re.subn(r'(?ms)^description:[^\n]*(?:\n[ \t]+[^\n]*)*', f'description: "Use only when the user explicitly requests {name}."', parts[1], count=1)
if count != 1:
    sys.exit(f'Missing description: {path}')
path.write_text('---' + front + '---' + parts[2], encoding='utf-8')
