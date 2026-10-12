#!/usr/bin/env bash
set -euo pipefail

HOST="${HOST:-127.0.0.1}"
USERS_PORT="${USERS_PORT:-8001}"
ORDERS_PORT="${ORDERS_PORT:-8002}"
PYTHON="${PYTHON:-python3}"
API_TOKEN="${API_TOKEN:-secret-token}"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
USERS_HEALTH="http://${HOST}:${USERS_PORT}/health"
ORDERS_HEALTH="http://${HOST}:${ORDERS_PORT}/health"

started_pids=()
cleanup() {
  for pid in "${started_pids[@]:-}"; do
    kill "$pid" 2>/dev/null || true
    wait "$pid" 2>/dev/null || true
  done
}
trap cleanup EXIT

wait_for() {
  local url="$1"
  local name="$2"
  local log="$3"
  for _ in $(seq 1 50); do
    curl -fsS "$url" >/dev/null 2>&1 && return 0
    sleep 0.2
  done
  echo "$name did not start"
  cat "$log" 2>/dev/null || true
  exit 1
}

cd "$ROOT"

if curl -fsS "$USERS_HEALTH" >/dev/null 2>&1; then
  echo "Using already running Users API at ${HOST}:${USERS_PORT}"
else
  echo "Starting Users API at ${HOST}:${USERS_PORT} (log: users.server.log)"
  API_TOKEN="$API_TOKEN" "$PYTHON" -m uvicorn app.main:app \
    --host "$HOST" --port "$USERS_PORT" \
    --app-dir "$ROOT/users_service" \
    >users.server.log 2>&1 &
  started_pids+=($!)
  wait_for "$USERS_HEALTH" "Users API" "users.server.log"
fi

if curl -fsS "$ORDERS_HEALTH" >/dev/null 2>&1; then
  echo "Using already running Orders API at ${HOST}:${ORDERS_PORT}"
else
  echo "Starting Orders API at ${HOST}:${ORDERS_PORT} (log: orders.server.log)"
  API_TOKEN="$API_TOKEN" USER_SERVICE_URL="http://${HOST}:${USERS_PORT}" \
    "$PYTHON" -m uvicorn app.main:app \
    --host "$HOST" --port "$ORDERS_PORT" \
    --app-dir "$ROOT/orders_service" \
    >orders.server.log 2>&1 &
  started_pids+=($!)
  wait_for "$ORDERS_HEALTH" "Orders API" "orders.server.log"
fi

"$@"
