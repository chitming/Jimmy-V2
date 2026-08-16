#!/usr/bin/env bash
# Idempotent Cloud Agent install for TDR (backend venv + frontend deps).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> TDR cloud install (root=$ROOT)"

if ! command -v python3 >/dev/null; then
  echo "python3 is required" >&2
  exit 1
fi
if ! command -v npm >/dev/null; then
  echo "npm is required" >&2
  exit 1
fi

# Backend venv
cd "$ROOT/backend"
if [[ ! -x .venv/bin/python ]]; then
  echo "==> Creating backend/.venv"
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip wheel setuptools
echo "==> Installing backend requirements"
if ! pip install -r requirements.txt; then
  echo "==> Full requirements failed; installing Windows/cloud core stack"
  pip install -r requirements-windows-core.txt
fi
deactivate || true

# Frontend
cd "$ROOT/frontend"
if [[ -f package-lock.json ]]; then
  echo "==> npm ci"
  npm ci
else
  echo "==> npm install"
  npm install
fi

# Optional: prebuild UI so packaged static serve works without Vite
echo "==> Building frontend"
npm run build
mkdir -p "$ROOT/backend/app/static"
if command -v rsync >/dev/null 2>&1; then
  rsync -a --delete "$ROOT/frontend/dist/" "$ROOT/backend/app/static/"
else
  rm -rf "$ROOT/backend/app/static"
  mkdir -p "$ROOT/backend/app/static"
  cp -a "$ROOT/frontend/dist/." "$ROOT/backend/app/static/"
fi

echo "==> Cloud install complete"
