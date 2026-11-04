#!/usr/bin/env bash
# Start the official XERJ local node with authentication enabled (no --insecure).
set -Eeuo pipefail
DATA="${XDG_DATA_HOME:-$HOME/.local/share}/scrooge-stack/xerj-data"
mkdir -p "$DATA"; chmod 700 "$DATA"
unset XERJ_CONFIG XERJ_BIND_ADDRESS
XERJ_BIN="$(command -v xerj || true)"
exec "${XERJ_BIN:-$HOME/.local/bin/xerj}" --config /dev/null --bind 127.0.0.1 --data-dir "$DATA"
