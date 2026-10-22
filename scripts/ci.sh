#!/usr/bin/env bash
# Локальный и GitHub-прогон одного и того же конвейера.
# 1. Сверить выгруженный OpenAPI с кодом.
# 2. Поднять Users API и Orders API.
# 3. Прогнать pytest и Newman, даже если pytest упал.
# 4. Собрать сводку из JUnit XML. Ненулевой код шагов 1–3 сохраняется.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export HOST="${HOST:-127.0.0.1}"
export USERS_PORT="${USERS_PORT:-8001}"
export ORDERS_PORT="${ORDERS_PORT:-8002}"
export PYTHON="${PYTHON:-python3}"

mkdir -p reports
rm -f reports/pytest.xml reports/newman.xml reports/ci-summary.md

pipeline_status=0

echo "==> OpenAPI: выгрузка и сверка с openapi/*.json"
"$PYTHON" scripts/export_openapi.py
if ! git diff --exit-code -- openapi/users.json openapi/orders.json; then
  echo "OpenAPI в репозитории не совпадает с кодом. Обновите файлы: make openapi" >&2
  pipeline_status=1
else
  echo "==> Сервисы, pytest и Newman"
  scripts/with_servers.sh scripts/ci_tests.sh || pipeline_status=$?
fi

echo "==> Сводка JUnit"
"$PYTHON" scripts/summarize_junit.py "$pipeline_status" || true
exit "$pipeline_status"
