import pytest

ORDERS = "/api/v1/orders"


def test_health(orders_api):
    response = orders_api.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "orders"}


def test_create_and_get_order(orders_api, auth_headers, order_payload, created_user):
    created = orders_api.post(ORDERS, json=order_payload, headers=auth_headers)

    assert created.status_code == 201
    body = created.json()
    assert isinstance(body["id"], int)
    assert body["user_id"] == created_user["id"]
    assert body["item"] == order_payload["item"]
    assert body["quantity"] == order_payload["quantity"]
    assert body["user"] == created_user
    assert created.headers["Location"] == f"{ORDERS}/{body['id']}"

    fetched = orders_api.get(f"{ORDERS}/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json() == body


def test_list_orders_contains_created(orders_api, created_order):
    response = orders_api.get(ORDERS)

    assert response.status_code == 200
    ids = {order["id"] for order in response.json()}
    assert created_order["id"] in ids


def test_get_missing_order_returns_404(orders_api):
    response = orders_api.get(f"{ORDERS}/999999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Order 999999 not found"}


def test_create_order_for_missing_user_returns_404(orders_api, auth_headers):
    response = orders_api.post(
        ORDERS,
        json={"user_id": 999999, "item": "Кружка", "quantity": 1},
        headers=auth_headers,
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "User 999999 not found"}


@pytest.mark.parametrize(
    "headers, expected_detail",
    [
        ({}, "Missing Authorization header"),
        ({"Authorization": "Bearer wrong-token"}, "Invalid token"),
    ],
    ids=["no-header", "wrong-token"],
)
def test_create_order_without_valid_token_returns_401(orders_api, order_payload, headers, expected_detail):
    response = orders_api.post(ORDERS, json=order_payload, headers=headers)

    assert response.status_code == 401
    assert response.json() == {"detail": expected_detail}


@pytest.mark.parametrize(
    "payload",
    [
        {"user_id": 1, "item": "", "quantity": 1},
        {"user_id": 1, "item": "Лампа", "quantity": 0},
        {"user_id": 0, "item": "Лампа", "quantity": 1},
        {"item": "Лампа", "quantity": 1},
        {"user_id": 1, "item": "Лампа", "quantity": 1, "extra": True},
    ],
    ids=["blank-item", "zero-qty", "zero-user", "missing-user", "unknown-field"],
)
def test_create_order_invalid_payload_returns_422(orders_api, auth_headers, payload):
    response = orders_api.post(ORDERS, json=payload, headers=auth_headers)

    assert response.status_code == 422
