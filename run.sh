#!/usr/bin/env bash
# datacenter-simulation launcher.
#   ./run.sh           start backend + frontend dev server for a live demo
#   ./run.sh --smoke   start backend + built frontend, run the Playwright smoke
#                      test against the live stack, then exit (CI / Gate 7)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
PREVIEW_PORT="${PREVIEW_PORT:-4173}"
MODE="demo"
[[ "${1:-}" == "--smoke" ]] && MODE="smoke"

mkdir -p .run
PGIDS=()

cleanup() {
  for pg in "${PGIDS[@]:-}"; do
    kill -TERM -"$pg" 2>/dev/null || true
  done
}
trap cleanup EXIT INT TERM

start_bg() { # start_bg <logfile> <command...>  -> records PGID, prints PID
  local log="$1"; shift
  setsid bash -c "$*" >"$log" 2>&1 &
  local pid=$!
  PGIDS+=("$pid")
  echo "$pid"
}

wait_for_health() { # wait_for_health <url> [tries]
  local url="$1" tries="${2:-80}"
  for ((i = 0; i < tries; i++)); do
    curl -sf "$url" >/dev/null 2>&1 && return 0
    sleep 0.5
  done
  return 1
}

# --- data ---
if [[ ! -f data/synthetic.csv || ! -f data/ground_truth.json ]]; then
  echo "[run] generating synthetic data..."
  PYTHONPATH=. uv run python data/generate.py
fi

# --- backend ---
echo "[run] starting backend on :$BACKEND_PORT ..."
start_bg ".run/backend.log" \
  "PYTHONPATH='$ROOT' uv run uvicorn api.main:app --host 127.0.0.1 --port $BACKEND_PORT --log-level warning" >/dev/null
if ! wait_for_health "http://127.0.0.1:$BACKEND_PORT/health"; then
  echo "[run] ERROR: backend did not become healthy. See .run/backend.log" >&2
  tail -n 30 .run/backend.log >&2 || true
  exit 1
fi
echo "[run] backend healthy at http://127.0.0.1:$BACKEND_PORT"

# --- frontend deps ---
if [[ ! -d frontend/node_modules ]]; then
  echo "[run] installing frontend deps (first run)..."
  (cd frontend && npm install)
fi

if [[ "$MODE" == "smoke" ]]; then
  echo "[run] building frontend..."
  (cd frontend && npm run build) >.run/frontend-build.log 2>&1 || {
    echo "[run] ERROR: frontend build failed. See .run/frontend-build.log" >&2
    tail -n 30 .run/frontend-build.log >&2; exit 1; }
  echo "[run] starting preview on :$PREVIEW_PORT ..."
  start_bg ".run/preview.log" \
    "cd '$ROOT/frontend' && npm run preview -- --port $PREVIEW_PORT --host 127.0.0.1" >/dev/null
  if ! wait_for_health "http://127.0.0.1:$PREVIEW_PORT"; then
    echo "[run] ERROR: preview server did not start. See .run/preview.log" >&2
    tail -n 30 .run/preview.log >&2; exit 1
  fi
  echo "[run] running Playwright smoke test against the live stack..."
  ( cd frontend && E2E_BASE_URL="http://127.0.0.1:$PREVIEW_PORT" \
      VITE_API_BASE="http://127.0.0.1:$BACKEND_PORT" npm run test:e2e )
  echo "[run] SMOKE PASSED (backend + frontend + Playwright all green)"
  exit 0
fi

# --- demo mode: frontend dev server ---
echo "[run] starting frontend dev server on :$FRONTEND_PORT ..."
start_bg ".run/frontend-dev.log" \
  "cd '$ROOT/frontend' && VITE_API_BASE='http://127.0.0.1:$BACKEND_PORT' npm run dev -- --port $FRONTEND_PORT --host 127.0.0.1" >/dev/null
wait_for_health "http://127.0.0.1:$FRONTEND_PORT" 80 || true

cat <<EOF

  datacenter-simulation is running:
    Backend : http://127.0.0.1:$BACKEND_PORT   (GET /health, POST /analyze)
    Frontend: http://127.0.0.1:$FRONTEND_PORT

  Open the frontend URL in a browser. Press Ctrl-C to stop everything.
EOF

# Wait until interrupted; the trap tears down both servers.
while true; do sleep 3600; done
