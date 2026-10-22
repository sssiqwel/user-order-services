import pytest

USERS = "/api/v1/users"


def test_health(users_api):
    response = users_api.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "users"}


def test_request_id_is_echoed(users_api):
    response = users_api.get("/health", headers={"X-Request-ID": "users-42"})

    assert response.headers["X-Request-ID"] == "users-42"


def test_list_users_contains_seed(users_api):
    response = users_api.get(USERS)

    assert response.status_code == 200
    emails = {user["email"] for user in response.json()}
    assert "anna@example.com" in emails


def test_create_and_get_user(users_api, auth_headers, user_payload):
    created = users_api.post(USERS, json=user_payload, headers=auth_headers)

    assert created.status_code == 201
    body = created.json()
    assert isinstance(body["id"], int)
    assert {k: v for k, v in body.items() if k != "id"} == user_payload
    assert created.headers["Location"] == f"{USERS}/{body['id']}"

    fetched = users_api.get(f"{USERS}/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json() == body


def test_create_user_normalizes_email_and_name(users_api, auth_headers):
    response = users_api.post(
        USERS,
        json={"name": "  Мария  ", "email": "  Maria@Example.COM  "},
        headers=auth_headers,
    )

    assert response.status_code == 201
    assert response.json()["name"] == "Мария"
    assert response.json()["email"] == "maria@example.com"


def test_create_user_duplicate_email_returns_409(users_api, auth_headers, created_user):
    response = users_api.post(
        USERS,
        json={"name": "Другой", "email": created_user["email"]},
        headers=auth_headers,
    )

    assert response.status_code == 409
    assert created_user["email"] in response.json()["detail"]


def test_get_missing_user_returns_404(users_api):
    response = users_api.get(f"{USERS}/999999")

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
def test_create_user_without_valid_token_returns_401(users_api, user_payload, headers, expected_detail):
    response = users_api.post(USERS, json=user_payload, headers=headers)

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert response.json() == {"detail": expected_detail}


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "", "email": "ok@example.com"},
        {"name": "   ", "email": "ok@example.com"},
        {"name": "Иван", "email": "not-an-email"},
        {"name": "Иван"},
        {"email": "ok@example.com", "extra": True},
    ],
    ids=["empty-name", "blank-name", "bad-email", "missing-email", "unknown-field"],
)
def test_create_user_invalid_payload_returns_422(users_api, auth_headers, payload):
    response = users_api.post(USERS, json=payload, headers=auth_headers)

    assert response.status_code == 422
