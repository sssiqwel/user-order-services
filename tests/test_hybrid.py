"""Гибридное интеграционное тестирование (сэндвич).

Снизу вверх драйвер вызывает хранилище напрямую: верхний HTTP-слой не участвует.
Сверху вниз TestClient бьёт в интерфейс, а модуль Users API заменён заглушкой.
Стыковка посередине — критичный сценарий создания заказа: интерфейс, проверка
данных и хранилище заказов настоящие, внешний пользовательский модуль — заглушка.
"""

from __future__ import annotations

import importlib
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "reports"
SERVICE_ROOTS = {
    str((ROOT / "users_service").resolve()),
    str((ROOT / "orders_service").resolve()),
}

FINDINGS: list[dict[str, Any]] = []
pytestmark = pytest.mark.hybrid


def record(
    defect_id: str,
    title: str,
    expected: str,
    actual: str,
    layer: str,
    severity: str,
    is_defect: bool,
) -> None:
    FINDINGS.append(
        {
            "id": defect_id,
            "title": title,
            "expected": expected,
            "actual": actual,
            "layer": layer,
            "severity": severity,
            "is_defect": is_defect,
        }
    )


@pytest.fixture(scope="session", autouse=True)
def persist_findings():
    REPORTS.mkdir(exist_ok=True)
    yield
    (REPORTS / "hybrid-findings.json").write_text(
        json.dumps(FINDINGS, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_service(name: str) -> SimpleNamespace:
    """Импортирует один сервис как пакет app, выгрузив предыдущий."""
    service_root = ROOT / f"{name}_service"
    for key in list(sys.modules):
        if key == "app" or key.startswith("app."):
            del sys.modules[key]
    sys.path[:] = [item for item in sys.path if str(Path(item).resolve()) not in SERVICE_ROOTS]
    sys.path.insert(0, str(service_root))
    main = importlib.import_module("app.main")
    storage_module = importlib.import_module("app.storage")
    models = importlib.import_module("app.models")
    auth = importlib.import_module("app.auth")
    users_client = importlib.import_module("app.users_client") if name == "orders" else None
    storage_module.storage.reset()
    return SimpleNamespace(
        name=name,
        main=main,
        app=main.app,
        models=models,
        auth=auth,
        users_client=users_client,
        db=storage_module.storage,
        storage_module=storage_module,
    )


@pytest.fixture
def orders():
    saved_path = sys.path.copy()
    box = load_service("orders")
    box.auth_headers = {"Authorization": f"Bearer {box.auth.API_TOKEN}"}
    try:
        with TestClient(box.app, raise_server_exceptions=False) as client:
            box.client = client
            yield box
    finally:
        box.db.reset()
        sys.path[:] = saved_path


@pytest.fixture
def users():
    saved_path = sys.path.copy()
    box = load_service("users")
    box.auth_headers = {"Authorization": f"Bearer {box.auth.API_TOKEN}"}
    try:
        with TestClient(box.app, raise_server_exceptions=False) as client:
            box.client = client
            yield box
    finally:
        box.db.reset()
        sys.path[:] = saved_path


class UserStub:
    """Заглушка нижнего модуля: get_user с заранее известным ответом."""

    def __init__(self, users_client) -> None:
        self._users_client = users_client
        self.calls: list[dict[str, Any]] = []
        self.replies: dict[int, tuple[int, dict | None]] = {}

    def __call__(self, user_id: int, request_id: str | None = None):
        self.calls.append({"user_id": user_id, "request_id": request_id})
        status, body = self.replies.get(user_id, (404, None))
        if status == 404:
            raise self._users_client.UserServiceError(404, f"User {user_id} not found")
        if status >= 500:
            raise self._users_client.UserServiceError(503, f"User service returned {status}")
        return self._users_client.UserLookup(body, 1.25)


class _StubHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:
        server = self.server
        server.paths.append(self.path)
        server.seen_headers.append({key.lower(): value for key, value in self.headers.items()})
        body = json.dumps(server.body).encode()
        self.send_response(server.status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args) -> None:
        return


class HttpStub:
    """HTTP-заглушка неготового Users API для проверки users_client."""

    def __init__(self, status: int, body: dict) -> None:
        self.status = status
        self.body = body
        self.paths: list[str] = []
        self.seen_headers: list[dict[str, str]] = []

    def __enter__(self) -> HttpStub:
        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), _StubHandler)
        self._httpd.status_code = self.status
        self._httpd.body = self.body
        self._httpd.paths = self.paths
        self._httpd.seen_headers = self.seen_headers
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        host, port = self._httpd.server_address
        self.url = f"http://{host}:{port}"
        return self

    def __exit__(self, *_) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()
        self._thread.join(timeout=3)


def test_hy_01_user_storage_via_driver():
    """Снизу вверх: драйвер вызывает хранилище пользователей, HTTP-интерфейса нет."""
    users = load_service("users")
    db = users.db
    try:
        seeded = db.list()
        assert {user.email for user in seeded} >= {"anna@example.com", "petr@example.com"}

        created = db.create(users.models.UserIn(name="  Мария  ", email="Maria@Test.dev"))
        assert created.id == 3
        assert created.name == "Мария"
        assert created.email == "maria@test.dev"
        assert db.get(created.id).email == "maria@test.dev"

        with pytest.raises(users.storage_module.DuplicateEmailError):
            db.create(users.models.UserIn(name="Другая Мария", email="maria@test.dev"))
        assert len(db.list()) == 3

        with pytest.raises(ValidationError):
            users.models.UserIn(name="   ", email="blank@example.com")
    finally:
        db.reset()


def test_hy_02_order_storage_without_user_module():
    """Снизу вверх: заказ пишется, хотя модуль пользователей ещё не подключён."""
    orders = load_service("orders")
    db = orders.db
    try:
        assert db.list() == []
        stored = db.create(
            orders.models.OrderIn(user_id=4242, item="Кабель", quantity=3),
        )
        assert stored.id == 1
        assert stored.user_id == 4242
        assert db.get(1).item == "Кабель"
        assert db.get(999) is None
        assert [order.id for order in db.list()] == [1]
    finally:
        db.reset()


def test_hy_03_validation_stops_before_storage():
    """Стык логики и данных: невалидный заказ не доходит до хранилища."""
    orders = load_service("orders")
    db = orders.db
    try:
        with pytest.raises(ValidationError):
            orders.models.OrderIn(user_id=0, item="   ", quantity=0)
        assert db.list() == []

        stored = db.create(orders.models.OrderIn(user_id=1, item="  Лампа  ", quantity=1))
        assert stored.item == "Лампа"
        assert len(db.list()) == 1
    finally:
        db.reset()


def test_hy_04_user_client_against_stub():
    """Середина: драйвер вызывает users_client, Users API — HTTP-заглушка."""
    with HttpStub(200, {"id": 5, "name": "Заглушка", "email": "stub@example.com"}) as stub:
        orders = load_service("orders")
        client = orders.users_client
        client.USER_SERVICE_URL = stub.url
        client.USER_SERVICE_TIMEOUT = 0.5

        found = client.get_user(5, request_id="hy-trace")
        assert found.user["email"] == "stub@example.com"
        assert found.elapsed_ms >= 0
        assert stub.paths == ["/api/v1/users/5"]
        assert stub.seen_headers[0].get("x-request-id") == "hy-trace"

        stub.status = 404
        stub._httpd.status_code = 404
        with pytest.raises(client.UserServiceError) as missing:
            client.get_user(5)
        assert missing.value.status_code == 404
        assert missing.value.detail == "User 5 not found"

    orders = load_service("orders")
    client = orders.users_client
    client.USER_SERVICE_URL = "http://127.0.0.1:9"
    client.USER_SERVICE_TIMEOUT = 0.3
    with pytest.raises(client.UserServiceError) as down:
        client.get_user(1)
    assert down.value.status_code == 503
    assert "unavailable" in down.value.detail


@pytest.mark.hybrid_defect
@pytest.mark.xfail(
    reason="HY-05: users_client превращает ответ заглушки 422 в 503 «invalid response»",
    strict=True,
)
def test_hy_05_client_error_from_stub_is_not_unavailable():
    """Неготовый Users API отвечает 422. Это ошибка запроса, а не недоступность сервиса."""
    body = {"detail": "id is invalid"}
    with HttpStub(422, body) as stub:
        orders = load_service("orders")
        client = orders.users_client
        client.USER_SERVICE_URL = stub.url
        client.USER_SERVICE_TIMEOUT = 0.5
        with pytest.raises(client.UserServiceError) as exc:
            client.get_user(7)
        actual = f"HTTP-статус заглушки 422 → UserServiceError {exc.value.status_code}: {exc.value.detail}"
        record(
            "HY-05",
            "Ответ 422 от заглушки Users API маскируется под недоступность сервиса",
            "UserServiceError со статусом 422, без подмены на 503",
            actual,
            "бизнес-логика orders_service/app/users_client.py",
            "high",
            exc.value.status_code != 422,
        )
        assert exc.value.status_code == 422, actual


def test_hy_06_create_order_across_three_layers(orders):
    """Критичный сценарий: интерфейс + логика + хранилище, пользователь — заглушка."""
    stub = UserStub(orders.users_client)
    stub.replies[1] = (200, {"id": 1, "name": "Анна Иванова", "email": "anna@example.com"})
    with patch.object(orders.main, "get_user", stub):
        created = orders.client.post(
            "/api/v1/orders",
            json={"user_id": 1, "item": "  Настольная лампа  ", "quantity": 2},
            headers={**orders.auth_headers, "X-Request-ID": "hy-create"},
        )
        assert created.status_code == 201, created.text
        body = created.json()
        assert body["item"] == "Настольная лампа"
        assert body["quantity"] == 2
        assert body["user"] == {"id": 1, "name": "Анна Иванова", "email": "anna@example.com"}
        assert created.headers["Location"] == f"/api/v1/orders/{body['id']}"
        assert created.headers["X-Request-ID"] == "hy-create"
        assert created.headers["X-User-Service-Time-Ms"] == "1.25"

        stored = orders.db.get(body["id"])
        assert stored is not None
        assert stored.user_id == 1
        assert stored.item == "Настольная лампа"
        assert stored.quantity == 2

        fetched = orders.client.get(f"/api/v1/orders/{body['id']}")
        assert fetched.status_code == 200, fetched.text
        assert fetched.json()["user"]["email"] == "anna@example.com"

    assert [call["user_id"] for call in stub.calls] == [1, 1]
    assert stub.calls[0]["request_id"] == "hy-create"
    record(
        "HY-OK-06",
        "Создание и чтение заказа через три слоя с заглушкой пользователя",
        "201/200, снимок из заглушки, строка в storage, Location и X-Request-ID",
        f"order={body['id']} storage_item={stored.item!r} stub_calls={len(stub.calls)}",
        "интерфейс main.py + модели + storage + заглушка get_user",
        "info",
        False,
    )


def test_hy_07_rejected_requests_do_not_cross_into_storage(orders):
    """Границы слоёв: 404 заглушки, 401 и 422 не оставляют заказ в хранилище."""
    stub = UserStub(orders.users_client)
    with patch.object(orders.main, "get_user", stub):
        missing = orders.client.post(
            "/api/v1/orders",
            json={"user_id": 50, "item": "Кружка", "quantity": 1},
            headers=orders.auth_headers,
        )
        assert missing.status_code == 404
        assert missing.json()["detail"] == "User 50 not found"
        assert orders.db.list() == []
        assert [call["user_id"] for call in stub.calls] == [50]

        stub.calls.clear()
        no_token = orders.client.post(
            "/api/v1/orders",
            json={"user_id": 1, "item": "Кружка", "quantity": 1},
        )
        assert no_token.status_code == 401
        assert orders.db.list() == []
        assert stub.calls == []

        invalid = orders.client.post(
            "/api/v1/orders",
            json={"user_id": 0, "item": " ", "quantity": 0},
            headers=orders.auth_headers,
        )
        assert invalid.status_code == 422
        assert orders.db.list() == []
        assert stub.calls == []


@pytest.mark.hybrid_defect
@pytest.mark.xfail(
    reason="HY-08: list_orders отдаёт 404 на весь список, хотя storage хранит оба заказа",
    strict=True,
)
def test_hy_08_list_failure_is_in_the_interface_not_in_storage(orders):
    """Один пользователь заглушки отсутствует. Данные обоих заказов на месте."""
    stub = UserStub(orders.users_client)
    stub.replies[1] = (200, {"id": 1, "name": "Анна Иванова", "email": "anna@example.com"})
    first = orders.db.create(orders.models.OrderIn(user_id=1, item="Лампа", quantity=1))
    second = orders.db.create(orders.models.OrderIn(user_id=2, item="Кружка", quantity=1))

    with patch.object(orders.main, "get_user", stub):
        one = orders.client.get(f"/api/v1/orders/{first.id}")
        listed = orders.client.get("/api/v1/orders")

    stored_ids = [order.id for order in orders.db.list()]
    actual = (
        f"storage={stored_ids}; GET /orders/{first.id} → {one.status_code}; "
        f"GET /orders → {listed.status_code} {listed.text[:180]}; "
        f"вызовы заглушки={[call['user_id'] for call in stub.calls]}"
    )
    record(
        "HY-08",
        "Список заказов падает целиком, хотя хранилище и чтение одного заказа работают",
        "HTTP 200 и в списке есть заказ пользователя id=1; строка user_id=2 остаётся в storage",
        actual,
        "интерфейс orders_service/app/main.py list_orders",
        "high",
        listed.status_code != 200,
    )
    assert stored_ids == [first.id, second.id]
    assert one.status_code == 200, one.text
    assert listed.status_code == 200, actual
    assert first.id in {item["id"] for item in listed.json()}


@pytest.mark.hybrid_defect
@pytest.mark.xfail(
    reason="HY-09: лишнее поле заглушки даёт 500, заказ уже записан в storage",
    strict=True,
)
def test_hy_09_extra_user_field_is_a_controlled_error(orders):
    """Заглушка неготового Users API добавляет поле, которого снимок заказа не ждёт."""
    stub = UserStub(orders.users_client)
    stub.replies[1] = (
        200,
        {"id": 1, "name": "Анна Иванова", "email": "anna@example.com", "phone": "+79990000000"},
    )
    with patch.object(orders.main, "get_user", stub):
        created = orders.client.post(
            "/api/v1/orders",
            json={"user_id": 1, "item": "Лампа", "quantity": 1},
            headers=orders.auth_headers,
        )
    stored = len(orders.db.list())
    actual = f"HTTP {created.status_code} {created.text[:180]}; заказов в storage={stored}"
    record(
        "HY-09",
        "Неожиданное поле пользователя заканчивается необработанной ошибкой и частичной записью",
        "Не 500: либо 201 и игнор лишнего поля, либо контролируемая ошибка без записи заказа",
        actual,
        "стык бизнес-логики UserSnapshot и интерфейса create_order",
        "high",
        not (
            (created.status_code == 201 and stored == 1)
            or (created.status_code != 500 and stored == 0)
        ),
    )
    assert created.status_code != 500, actual
    assert stored == (1 if created.status_code == 201 else 0)


@pytest.mark.hybrid_defect
@pytest.mark.xfail(
    reason="HY-10: заказ есть в storage, но интерфейс отвечает 404 и без времени вызова",
    strict=True,
)
def test_hy_10_missing_user_is_not_a_missing_order(orders):
    """Данные заказа целы. Заглушка говорит, что пользователя нет. Путаются два разных 404."""
    stored = orders.db.create(orders.models.OrderIn(user_id=8, item="Кружка", quantity=1))
    stub = UserStub(orders.users_client)
    with patch.object(orders.main, "get_user", stub):
        missing_order = orders.client.get("/api/v1/orders/999999")
        fetched = orders.client.get(f"/api/v1/orders/{stored.id}")

    has_timing = "X-User-Service-Time-Ms" in fetched.headers
    actual = (
        f"storage.get({stored.id})={'есть' if orders.db.get(stored.id) else 'нет'}; "
        f"нет заказа → {missing_order.status_code} {missing_order.json()}; "
        f"есть заказ, нет пользователя → {fetched.status_code} {fetched.text[:160]}; "
        f"timing={has_timing}"
    )
    record(
        "HY-10",
        "Существующий заказ получает тот же 404, что и отсутствующий",
        "Заказ найден в storage: статус не 404 и есть X-User-Service-Time-Ms",
        actual,
        "интерфейс orders_service/app/main.py get_order / enrich_order",
        "high",
        fetched.status_code == 404 or not has_timing,
    )
    assert orders.db.get(stored.id) is not None
    assert missing_order.status_code == 404
    assert "Order" in missing_order.json()["detail"]
    assert fetched.status_code != 404, actual
    assert has_timing


def test_hy_11_health_does_not_touch_the_lower_layer(orders):
    """Аномалия интерфейса: /health не вызывает нижний модуль, чтение заказа — вызывает."""
    orders.db.create(orders.models.OrderIn(user_id=1, item="Лампа", quantity=1))
    stub = UserStub(orders.users_client)
    stub.replies[1] = (503, None)
    with patch.object(orders.main, "get_user", stub):
        health = orders.client.get("/health")
        calls_after_health = len(stub.calls)
        fetched = orders.client.get("/api/v1/orders/1")

    record(
        "HY-11",
        "GET /health не смотрит на заглушку пользователя и отвечает 200",
        "Либо readiness видит отказ нижнего слоя, либо health явно отделён от готовности",
        f"health={health.status_code} {health.json()}; вызовов заглушки до чтения={calls_after_health}; "
        f"GET /orders/1 → {fetched.status_code}",
        "интерфейс orders_service/app/main.py health",
        "medium",
        health.status_code == 200 and calls_after_health == 0 and fetched.status_code == 503,
    )
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}
    assert calls_after_health == 0
    assert fetched.status_code == 503


def test_hy_12_list_calls_the_stub_once_per_order(orders):
    """Аномалия интерфейса: список вызывает заглушку на каждый заказ, даже одного пользователя."""
    stub = UserStub(orders.users_client)
    stub.replies[1] = (200, {"id": 1, "name": "Анна Иванова", "email": "anna@example.com"})
    with patch.object(orders.main, "get_user", stub):
        for index in range(3):
            created = orders.client.post(
                "/api/v1/orders",
                json={"user_id": 1, "item": f"Товар-{index}", "quantity": 1},
                headers=orders.auth_headers,
            )
            assert created.status_code == 201, created.text
        stub.calls.clear()
        listed = orders.client.get("/api/v1/orders")

    assert listed.status_code == 200, listed.text
    user_ids = {call["user_id"] for call in stub.calls}
    record(
        "HY-12",
        "GET /orders вызывает заглушку пользователя по разу на каждый заказ",
        "Один пользователь в списке — один вызов нижнего модуля на запрос",
        f"заказов={len(listed.json())}, вызовов заглушки={len(stub.calls)}, user_id={sorted(user_ids)}",
        "интерфейс orders_service/app/main.py list_orders",
        "medium",
        len(stub.calls) > len(user_ids),
    )
    assert len(listed.json()) == 3
    assert user_ids == {1}


def test_hy_13_duplicate_email_is_raised_below_and_mapped_above(users):
    """Users API: драйвер видит DuplicateEmailError, интерфейс переводит её в 409."""
    db = users.db
    with pytest.raises(users.storage_module.DuplicateEmailError):
        db.create(users.models.UserIn(name="Вторая Анна", email="anna@example.com"))
    assert len(db.list()) == 2

    via_stub = users.client.post(
        "/api/v1/users",
        json={"name": "Заглушка", "email": "stub@example.com"},
        headers=users.auth_headers,
    )
    assert via_stub.status_code == 201, via_stub.text

    def rejected_create(_data):
        raise users.storage_module.DuplicateEmailError("stub@example.com")

    with patch.object(db, "create", rejected_create):
        mapped = users.client.post(
            "/api/v1/users",
            json={"name": "Ещё одна", "email": "other@example.com"},
            headers=users.auth_headers,
        )
    assert mapped.status_code == 409
    assert "already exists" in mapped.json()["detail"]

    duplicate = users.client.post(
        "/api/v1/users",
        json={"name": "Пётр ещё раз", "email": "PETR@example.com"},
        headers=users.auth_headers,
    )
    assert duplicate.status_code == 409
    assert len(db.list()) == 3
