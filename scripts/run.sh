#!/usr/bin/env bash
set -euo pipefail

HOST="${HOST:-127.0.0.1}"
USERS_PORT="${USERS_PORT:-8001}"
ORDERS_PORT="${ORDERS_PORT:-8002}"
PYTHON="${PYTHON:-python3}"
API_TOKEN="${API_TOKEN:-secret-token}"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

cleanup() {
  kill "${users_pid:-}" "${orders_pid:-}" 2>/dev/null || true
  wait "${users_pid:-}" "${orders_pid:-}" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "Users API  http://${HOST}:${USERS_PORT}/docs"
echo "Orders API http://${HOST}:${ORDERS_PORT}/docs"

API_TOKEN="$API_TOKEN" "$PYTHON" -m uvicorn app.main:app \
  --host "$HOST" --port "$USERS_PORT" --reload \
  --app-dir "$ROOT/users_service" &
users_pid=$!

API_TOKEN="$API_TOKEN" USER_SERVICE_URL="http://${HOST}:${USERS_PORT}" \
  "$PYTHON" -m uvicorn app.main:app \
  --host "$HOST" --port "$ORDERS_PORT" --reload \
  --app-dir "$ROOT/orders_service" &
orders_pid=$!

wait
