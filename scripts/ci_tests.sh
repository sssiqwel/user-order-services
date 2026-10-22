#!/usr/bin/env bash
# Шаги прогона, которые выполняются, когда оба сервиса уже отвечают на /health.
# Код выхода — код pytest, если он ненулевой, иначе код Newman.
set +e

"$PYTHON" -m pytest
pytest_status=$?

npx --yes newman@6.2.1 run postman/user_order.postman_collection.json \
  -e postman/local.postman_environment.json \
  --env-var "usersBaseUrl=http://${HOST}:${USERS_PORT}" \
  --env-var "ordersBaseUrl=http://${HOST}:${ORDERS_PORT}" \
  --reporters cli,junit \
  --reporter-junit-export reports/newman.xml
newman_status=$?

if [ "$pytest_status" -ne 0 ]; then
  exit "$pytest_status"
fi
exit "$newman_status"
