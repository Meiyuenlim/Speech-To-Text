#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
[[ -x .venv/bin/python ]] || { echo "Run ./scripts/setup.sh first."; exit 1; }

cleanup() { kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true; }
trap cleanup EXIT INT TERM
.venv/bin/python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port "${BACKEND_PORT:-8000}" &
BACKEND_PID=$!
(cd frontend && npm run dev -- --host 127.0.0.1) &
FRONTEND_PID=$!
echo "Backend: http://127.0.0.1:${BACKEND_PORT:-8000}"
echo "Frontend: http://127.0.0.1:5173"
wait "$BACKEND_PID" "$FRONTEND_PID"
