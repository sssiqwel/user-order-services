VENV   ?= .venv
PYTHON ?= $(VENV)/bin/python
HOST   ?= 127.0.0.1
USERS_PORT  ?= 8001
ORDERS_PORT ?= 8002

export HOST USERS_PORT ORDERS_PORT PYTHON

COLLECTION  = postman/user_order.postman_collection.json
ENVIRONMENT = postman/local.postman_environment.json
NEWMAN      = npx --yes newman@6.2.1 run $(COLLECTION) -e $(ENVIRONMENT) \
              --env-var usersBaseUrl=http://$(HOST):$(USERS_PORT) \
              --env-var ordersBaseUrl=http://$(HOST):$(ORDERS_PORT) \
              --reporters cli,junit --reporter-junit-export reports/newman.xml

.PHONY: help install run run-users run-orders test newman check openapi clean

$(VENV)/bin/python:
	python3 -m venv $(VENV)

install: $(VENV)/bin/python
	$(PYTHON) -m pip install -r requirements.txt

run:
	scripts/run.sh

run-users:
	API_TOKEN=$${API_TOKEN:-secret-token} $(PYTHON) -m uvicorn app.main:app \
		--host $(HOST) --port $(USERS_PORT) --reload --app-dir users_service

run-orders:
	API_TOKEN=$${API_TOKEN:-secret-token} USER_SERVICE_URL=http://$(HOST):$(USERS_PORT) \
		$(PYTHON) -m uvicorn app.main:app \
		--host $(HOST) --port $(ORDERS_PORT) --reload --app-dir orders_service

test:
	$(PYTHON) -m pytest

newman:
	@mkdir -p reports
	scripts/with_servers.sh $(NEWMAN)

check:
	@mkdir -p reports
	scripts/with_servers.sh sh -c '$(PYTHON) -m pytest && $(NEWMAN)'

openapi:
	$(PYTHON) scripts/export_openapi.py

clean:
	rm -rf reports users.server.log orders.server.log server.log .pytest_cache

help:
	@echo "make install     создать .venv и поставить зависимости"
	@echo "make run         оба сервиса: Users :$(USERS_PORT), Orders :$(ORDERS_PORT)"
	@echo "make test        pytest; если сервисы не запущены, тесты поднимут их сами"
	@echo "make newman      Postman-коллекция через Newman"
	@echo "make check       pytest + newman"
	@echo "make openapi     обновить openapi/*.json"
