from conftest import USER_FETCH_SLO_MS

ORDERS = "/api/v1/orders"


def test_orders_service_fetches_user_by_id(orders_api, auth_headers, created_user, order_payload):
    """Успех: сервис заказов запрашивает пользователя в Users API по id."""
    response = orders_api.post(ORDERS, json=order_payload, headers=auth_headers)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["user_id"] == created_user["id"]
    assert body["user"]["id"] == created_user["id"]
    assert body["user"]["name"] == created_user["name"]
    assert body["user"]["email"] == created_user["email"]

    fetched = orders_api.get(f"{ORDERS}/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["user"] == created_user


def test_orders_return_503_when_users_service_is_unavailable(isolated_orders_api, auth_headers):
    """Ошибка: Users API недоступен — Orders API отвечает 503, заказ не создаётся."""
    response = isolated_orders_api.post(
        ORDERS,
        json={"user_id": 1, "item": "Кружка", "quantity": 1},
        headers=auth_headers,
    )

    assert response.status_code == 503
    assert "unavailable" in response.json()["detail"].lower()

    listed = isolated_orders_api.get(ORDERS)
    assert listed.status_code == 200
    assert listed.json() == []


def test_user_fetch_response_time_is_within_slo(orders_api, created_order):
    """Время отклика межсервисного вызова Users API укладывается в SLO."""
    response = orders_api.get(f"{ORDERS}/{created_order['id']}")

    assert response.status_code == 200
    assert "X-User-Service-Time-Ms" in response.headers
    fetch_ms = float(response.headers["X-User-Service-Time-Ms"])
    total_ms = response.elapsed.total_seconds() * 1000

    assert fetch_ms >= 0
    assert fetch_ms < USER_FETCH_SLO_MS
    assert total_ms < USER_FETCH_SLO_MS + 500
