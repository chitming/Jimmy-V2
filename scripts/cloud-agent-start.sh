#!/usr/bin/env bash
# Start TDR backend + frontend for Cloud Agents (idempotent, stays attached).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

BACKEND_LOG="/tmp/tdr-backend.log"
FRONTEND_LOG="/tmp/tdr-frontend.log"

echo "==> Reconciling ports 8000 / 5173"
pkill -f "uvicorn app.main:app" 2>/dev/null || true
pkill -f "vite" 2>/dev/null || true
sleep 1

echo "==> Starting backend on :8000"
cd "$ROOT/backend"
# shellcheck disable=SC1091
source .venv/bin/activate
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload \
  >"$BACKEND_LOG" 2>&1 &
deactivate || true

echo "==> Starting frontend on :5173"
cd "$ROOT/frontend"
nohup npm run dev -- --host 0.0.0.0 --port 5173 \
  >"$FRONTEND_LOG" 2>&1 &

echo "==> Waiting for readiness"
for _ in $(seq 1 90); do
  be=0
  fe=0
  if curl -sf -o /dev/null --max-time 2 "http://127.0.0.1:8000/api/stats"; then be=1; fi
  if curl -sf -o /dev/null --max-time 2 "http://127.0.0.1:5173/"; then fe=1; fi
  if [[ "$be" -eq 1 && "$fe" -eq 1 ]]; then
    echo "==> TDR ready: API http://127.0.0.1:8000  UI http://127.0.0.1:5173"
    # Stay attached so the start phase keeps services supervised.
    exec tail -n 20 -F "$BACKEND_LOG" "$FRONTEND_LOG"
  fi
  sleep 1
done

echo "Backend or frontend failed to become ready" >&2
echo "---- backend log ----" >&2
tail -n 80 "$BACKEND_LOG" >&2 || true
echo "---- frontend log ----" >&2
tail -n 80 "$FRONTEND_LOG" >&2 || true
exit 1
