#!/usr/bin/env python3
"""Exit 0 for a matching user MCP entry, 1 when absent, 2 on conflict."""
import json
from pathlib import Path
import sys

try:
    path, name, expected = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
    data = json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else {}
    if not isinstance(data, dict) or not isinstance(data.get('mcpServers', {}), dict):
        raise ValueError('invalid Gemini settings structure')
    entry = data.get('mcpServers', {}).get(name)
    if entry is None:
        sys.exit(1)
    if not isinstance(entry, dict):
        raise ValueError('invalid MCP entry')
    actual = entry.get('url', entry.get('httpUrl')) if name == 'deploychan' else entry.get('command')
    if actual != expected:
        raise ValueError(f'existing {name} differs; preserving it')
    if name == 'xerj' and entry.get('args', []) != []:
        raise ValueError('existing xerj arguments differ; preserving it')
    sys.exit(0)
except (OSError, UnicodeError, ValueError, IndexError) as exc:
    print(f'Cannot validate Gemini MCP: {exc}', file=sys.stderr)
    sys.exit(2)
