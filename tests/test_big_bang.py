"""Интеграционное тестирование методом «большого взрыва».

Все модули (Users: models/storage/auth/API; Orders: models/storage/auth/
users_client/API) поднимаются одновременно, без заглушек и без поэтапного
подключения. Тесты работают только с уже собранной системой.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field
from typing import Any

import pytest
import requests

from conftest import ApiClient, ROOT, _start_service, _stop

FINDINGS: list[dict[str, Any]] = []
REPORTS = ROOT / "reports"
USERS_PORT = os.getenv("BIGBANG_USERS_PORT", "28001")
ORDERS_PORT = os.getenv("BIGBANG_ORDERS_PORT", "28002")
HOST = os.getenv("HOST", "127.0.0.1")
TOKEN = os.getenv("API_TOKEN", "secret-token")


def record(
    defect_id: str,
    title: str,
    expected: str,
    actual: str,
    modules: str,
    severity: str,
    is_defect: bool,
) -> None:
    FINDINGS.append(
        {
            "id": defect_id,
            "title": title,
            "expected": expected,
            "actual": actual,
            "modules": modules,
            "severity": severity,
            "is_defect": is_defect,
        }
    )


@pytest.fixture(scope="session", autouse=True)
def persist_findings():
    REPORTS.mkdir(exist_ok=True)
    yield
    (REPORTS / "big-bang-findings.json").write_text(
        json.dumps(FINDINGS, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


@dataclass
class BangSystem:
    """Полная сборка: оба сервиса, реальный HTTP между ними."""

    users_url: str
    orders_url: str
    users: ApiClient
    orders: ApiClient
    auth: dict[str, str]
    users_proc: Any
    orders_proc: Any
    users_port: str
    notes: list[dict[str, Any]] = field(default_factory=list)

    def restart_users(self) -> None:
        _stop(self.users_proc)
        self.users_proc = _start_service(ROOT / "users_service", self.users_port)

    def stop_users(self) -> None:
        _stop(self.users_proc)
        self.users_proc = None

    def unique_user(self) -> dict[str, str]:
        return {
            "name": "Большой Взрыв",
            "email": f"bang-{uuid.uuid4().hex[:10]}@example.com",
        }


def _boot(users_port: str, orders_port: str) -> BangSystem:
    users_url = f"http://{HOST}:{users_port}"
    orders_url = f"http://{HOST}:{orders_port}"
    users_proc = _start_service(ROOT / "users_service", users_port)
    orders_proc = _start_service(
        ROOT / "orders_service",
        orders_port,
        extra_env={
            "USER_SERVICE_URL": users_url,
            "USER_SERVICE_TIMEOUT": "2",
        },
    )
    return BangSystem(
        users_url=users_url,
        orders_url=orders_url,
        users=ApiClient(users_url),
        orders=ApiClient(orders_url),
        auth={"Authorization": f"Bearer {TOKEN}"},
        users_proc=users_proc,
        orders_proc=orders_proc,
        users_port=users_port,
    )


def _shutdown(system: BangSystem) -> None:
    system.users.close()
    system.orders.close()
    _stop(system.orders_proc)
    _stop(system.users_proc)


@pytest.fixture(scope="module")
def bang() -> BangSystem:
    """Один этап: Users API и Orders API стартуют вместе."""
    system = _boot(USERS_PORT, ORDERS_PORT)
    try:
        yield system
    finally:
        _shutdown(system)


@pytest.fixture
def fresh_bang() -> BangSystem:
    """Изолированная сборка для разрушающих сценариев (рестарт, останов)."""
    system = _boot(
        os.getenv("BIGBANG_FRESH_USERS_PORT", "28011"),
        os.getenv("BIGBANG_FRESH_ORDERS_PORT", "28012"),
    )
    try:
        yield system
    finally:
        _shutdown(system)


@pytest.mark.bigbang
def test_bb_01_all_modules_together_happy_path(bang: BangSystem):
    """Все модули сразу: health, seed, auth, валидация, storage, HTTP-клиент, обогащение."""
    users_health = bang.users.get("/health")
    orders_health = bang.orders.get("/health")
    assert users_health.status_code == 200 and users_health.json() == {"status": "ok"}
    assert orders_health.status_code == 200 and orders_health.json() == {"status": "ok"}

    listed_users = bang.users.get("/api/v1/users")
    assert listed_users.status_code == 200
    emails = {u["email"] for u in listed_users.json()}
    assert {"anna@example.com", "petr@example.com"} <= emails

    created_user = bang.users.post(
        "/api/v1/users",
        json=bang.unique_user(),
        headers={**bang.auth, "X-Request-ID": "bang-create-user"},
    )
    assert created_user.status_code == 201, created_user.text
    user = created_user.json()
    assert created_user.headers["Location"] == f"/api/v1/users/{user['id']}"
    assert created_user.headers["X-Request-ID"] == "bang-create-user"

    fetched_user = bang.users.get(f"/api/v1/users/{user['id']}")
    assert fetched_user.status_code == 200
    assert fetched_user.json() == user

    order_body = {"user_id": user["id"], "item": "Настольная лампа", "quantity": 2}
    created_order = bang.orders.post(
        "/api/v1/orders",
        json=order_body,
        headers={**bang.auth, "X-Request-ID": "bang-create-order"},
    )
    assert created_order.status_code == 201, created_order.text
    order = created_order.json()
    assert order["user"] == user
    assert order["item"] == "Настольная лампа"
    assert created_order.headers["Location"] == f"/api/v1/orders/{order['id']}"
    assert created_order.headers["X-Request-ID"] == "bang-create-order"
    assert "X-User-Service-Time-Ms" in created_order.headers
    assert float(created_order.headers["X-User-Service-Time-Ms"]) >= 0

    fetched_order = bang.orders.get(f"/api/v1/orders/{order['id']}")
    assert fetched_order.status_code == 200
    assert fetched_order.json()["user"] == user
    assert "X-User-Service-Time-Ms" in fetched_order.headers

    listed_orders = bang.orders.get("/api/v1/orders")
    assert listed_orders.status_code == 200
    assert order["id"] in {item["id"] for item in listed_orders.json()}
    for item in listed_orders.json():
        assert "user" in item and "email" in item["user"]

    record(
        "BB-OK-01",
        "Сквозной happy path на полной сборке",
        "201/200, вложенный user, Location, X-Request-ID, X-User-Service-Time-Ms",
        f"user={user['id']} order={order['id']} status=ok",
        "auth, models, storage, middleware, users_client, оба API",
        "info",
        False,
    )


@pytest.mark.bigbang
def test_bb_02_error_paths_on_fully_assembled_system(bang: BangSystem):
    """Негативные проверки тоже идут по живым модулям, без изоляции."""
    missing_user = bang.orders.post(
        "/api/v1/orders",
        json={"user_id": 999999, "item": "Кружка", "quantity": 1},
        headers=bang.auth,
    )
    assert missing_user.status_code == 404
    assert missing_user.json() == {"detail": "User 999999 not found"}

    no_token = bang.orders.post(
        "/api/v1/orders",
        json={"user_id": 1, "item": "Кружка", "quantity": 1},
    )
    assert no_token.status_code == 401

    bad_token = bang.users.post(
        "/api/v1/users",
        json=bang.unique_user(),
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert bad_token.status_code == 401

    invalid = bang.orders.post(
        "/api/v1/orders",
        json={"user_id": 0, "item": " ", "quantity": 0},
        headers=bang.auth,
    )
    assert invalid.status_code == 422

    missing_order = bang.orders.get("/api/v1/orders/999999")
    assert missing_order.status_code == 404
    assert missing_order.json() == {"detail": "Order 999999 not found"}


@pytest.mark.bigbang
def test_bb_03_n_plus_one_user_fetches_on_list(bang: BangSystem):
    """Аномалия производительности: список заказов вызывает Users API на каждый элемент."""
    user = bang.users.post("/api/v1/users", json=bang.unique_user(), headers=bang.auth).json()
    created_ids = []
    for i in range(4):
        resp = bang.orders.post(
            "/api/v1/orders",
            json={"user_id": user["id"], "item": f"Товар-{i}", "quantity": 1},
            headers=bang.auth,
        )
        assert resp.status_code == 201
        created_ids.append(resp.json()["id"])

    one = bang.orders.get(f"/api/v1/orders/{created_ids[0]}")
    listed = bang.orders.get("/api/v1/orders")
    assert one.status_code == 200 and listed.status_code == 200

    one_ms = float(one.headers["X-User-Service-Time-Ms"])
    list_ms = float(listed.headers["X-User-Service-Time-Ms"])
    n_orders = len(listed.json())
    is_defect = n_orders >= 4 and list_ms > one_ms * 2

    record(
        "BB-03",
        "N+1 межсервисных вызовов при GET /orders",
        "Список заказов не должен линейно умножать время вызова Users API",
        f"один заказ={one_ms:.2f} мс, список из {n_orders}={list_ms:.2f} мс",
        "orders.main.list_orders + users_client.get_user",
        "medium",
        is_defect,
    )
    assert list_ms >= 0
    assert n_orders >= 4


@pytest.mark.bigbang
@pytest.mark.bigbang_defect
@pytest.mark.xfail(
    reason=(
        "BB-04: GET /orders отвечает 404 User not found на весь список, "
        "если исчез хотя бы один пользователь"
    ),
    strict=True,
)
def test_bb_04_list_orders_fails_entirely_if_one_user_disappears(fresh_bang: BangSystem):
    """Дефект: пропажа одного пользователя роняет весь список заказов.

    Ожидаемое поведение: 200 и заказы с живыми пользователями.
    Фактическое: 404 на весь GET /orders.
    """
    seed_order = fresh_bang.orders.post(
        "/api/v1/orders",
        json={"user_id": 1, "item": "Лампа для Анны", "quantity": 1},
        headers=fresh_bang.auth,
    )
    assert seed_order.status_code == 201, seed_order.text

    transient = fresh_bang.users.post(
        "/api/v1/users", json=fresh_bang.unique_user(), headers=fresh_bang.auth
    )
    assert transient.status_code == 201
    lost_user_id = transient.json()["id"]
    lost_order = fresh_bang.orders.post(
        "/api/v1/orders",
        json={"user_id": lost_user_id, "item": "Временный товар", "quantity": 1},
        headers=fresh_bang.auth,
    )
    assert lost_order.status_code == 201

    fresh_bang.restart_users()

    still_there = fresh_bang.users.get("/api/v1/users/1")
    gone = fresh_bang.users.get(f"/api/v1/users/{lost_user_id}")
    assert still_there.status_code == 200
    assert gone.status_code == 404

    listed = fresh_bang.orders.get("/api/v1/orders")
    expected = "HTTP 200, в списке остаётся заказ пользователя id=1"
    actual = f"HTTP {listed.status_code}: {listed.text[:300]}"
    record(
        "BB-04",
        "Каскадный отказ GET /api/v1/orders при исчезновении одного пользователя",
        expected,
        actual,
        "orders.storage + orders.main.enrich_order + users.storage (in-memory)",
        "high",
        listed.status_code != 200,
    )

    assert listed.status_code == 200, (
        "Большой взрыв: список заказов недоступен целиком "
        f"({listed.status_code} {listed.text}). "
        "Неясно, виноваты storage Users, enrich_order или users_client."
    )
    ids = {item["id"] for item in listed.json()}
    assert seed_order.json()["id"] in ids


@pytest.mark.bigbang
@pytest.mark.bigbang_defect
@pytest.mark.xfail(
    reason=(
        "BB-05: GET существующего заказа после рестарта Users даёт 404 User not found "
        "без X-User-Service-Time-Ms"
    ),
    strict=True,
)
def test_bb_05_get_order_masks_missing_user_as_order_404(fresh_bang: BangSystem):
    """Дефект: 404 «User not found» на существующем заказе. Клиент путает причину."""
    user = fresh_bang.users.post(
        "/api/v1/users", json=fresh_bang.unique_user(), headers=fresh_bang.auth
    ).json()
    created = fresh_bang.orders.post(
        "/api/v1/orders",
        json={"user_id": user["id"], "item": "Кружка", "quantity": 1},
        headers=fresh_bang.auth,
    )
    assert created.status_code == 201
    order_id = created.json()["id"]

    fresh_bang.restart_users()

    fetched = fresh_bang.orders.get(f"/api/v1/orders/{order_id}")
    has_timing = "X-User-Service-Time-Ms" in fetched.headers
    record(
        "BB-05",
        "GET заказа после рестарта Users маскирует пропажу пользователя под 404",
        "Заказ существует: 200 со снимком либо 409/410 «пользователь недоступен», "
        "заголовок X-User-Service-Time-Ms сохраняется",
        f"HTTP {fetched.status_code} {fetched.text[:200]}; timing_header={has_timing}",
        "orders.main.get_order + enrich_order + users_client (404→HTTPException)",
        "high",
        fetched.status_code == 404 and not has_timing,
    )

    assert fetched.status_code == 200, (
        f"Заказ {order_id} есть в Orders, но ответ {fetched.status_code}: {fetched.text}. "
        "По коду 404 нельзя понять, нет заказа или нет пользователя."
    )


@pytest.mark.bigbang
def test_bb_06_health_stays_ok_while_integration_is_broken(fresh_bang: BangSystem):
    """Аномалия: /health Orders не проверяет Users API."""
    created = fresh_bang.orders.post(
        "/api/v1/orders",
        json={"user_id": 1, "item": "Лампа", "quantity": 1},
        headers=fresh_bang.auth,
    )
    assert created.status_code == 201
    order_id = created.json()["id"]

    fresh_bang.stop_users()

    health = fresh_bang.orders.get("/health")
    order = fresh_bang.orders.get(f"/api/v1/orders/{order_id}")
    listed = fresh_bang.orders.get("/api/v1/orders")

    try:
        users_health = fresh_bang.users.get("/health")
        users_up = users_health.status_code == 200
    except requests.RequestException:
        users_up = False

    record(
        "BB-06",
        "Orders /health=200 при недоступном Users API",
        "Зависимость должна быть видна (readiness 503) либо явно разделена liveness/readiness",
        f"orders_health={health.status_code}, get_order={order.status_code}, "
        f"list={listed.status_code}, users_up={users_up}",
        "orders.main.health vs users_client.get_user",
        "medium",
        health.status_code == 200 and order.status_code == 503 and not users_up,
    )

    assert health.status_code == 200
    assert order.status_code == 503
    assert listed.status_code == 503
    assert not users_up


@pytest.mark.bigbang
def test_bb_07_request_id_propagates_across_services(bang: BangSystem):
    """Сквозная трассировка: Orders передаёт X-Request-ID в Users API."""
    trace = f"bang-trace-{uuid.uuid4().hex[:8]}"
    created = bang.orders.post(
        "/api/v1/orders",
        json={"user_id": 1, "item": "Трассировка", "quantity": 1},
        headers={**bang.auth, "X-Request-ID": trace},
    )
    assert created.status_code == 201
    assert created.headers["X-Request-ID"] == trace

    fetched = bang.orders.get(
        f"/api/v1/orders/{created.json()['id']}",
        headers={"X-Request-ID": trace},
    )
    assert fetched.status_code == 200
    assert fetched.headers["X-Request-ID"] == trace
