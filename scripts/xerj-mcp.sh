#!/usr/bin/env bash
# Runs upstream XERJ's MCP adapter; no custom MCP service is implemented here.
set -Eeuo pipefail
XERJ_ROOT="${XDG_DATA_HOME:-$HOME/.local/share}/scrooge-stack"
XERJ_BIN="$(command -v xerj || true)"
XERJ_BIN="${XERJ_BIN:-$HOME/.local/bin/xerj}"
export XERJ_URL="http://127.0.0.1:9200"
[[ -s "$XERJ_ROOT/xerj-data/admin.key" ]] || { echo 'XERJ admin.key is missing; start the authenticated node first' >&2; exit 1; }
XERJ_AUTH="ApiKey $(cat "$XERJ_ROOT/xerj-data/admin.key")"
export XERJ_AUTH
exec "$XERJ_BIN" mcp
