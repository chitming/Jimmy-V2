#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PORT="${1:-8787}"
cd "$ROOT/tools/dwf-viewer"
echo "DWF viewer: http://127.0.0.1:${PORT}"
echo "Open a .dwf / .dwfx file from the page."
exec python3 -m http.server "$PORT" --bind 0.0.0.0
