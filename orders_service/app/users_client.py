import os
import time

import requests

USER_SERVICE_URL = os.getenv("USER_SERVICE_URL", "http://127.0.0.1:8001").rstrip("/")
USER_SERVICE_TIMEOUT = float(os.getenv("USER_SERVICE_TIMEOUT", "2"))


class UserServiceError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class UserLookup:
    def __init__(self, user: dict, elapsed_ms: float) -> None:
        self.user = user
        self.elapsed_ms = elapsed_ms


def get_user(user_id: int, request_id: str | None = None) -> UserLookup:
    url = f"{USER_SERVICE_URL}/api/v1/users/{user_id}"
    headers = {"Accept": "application/json"}
    if request_id:
        headers["X-Request-ID"] = request_id

    started = time.perf_counter()
    try:
        response = requests.get(url, timeout=USER_SERVICE_TIMEOUT, headers=headers)
    except requests.RequestException as exc:
        raise UserServiceError(
            503,
            f"User service is unavailable: {exc}",
        ) from exc
    elapsed_ms = (time.perf_counter() - started) * 1000

    if response.status_code == 404:
        raise UserServiceError(404, f"User {user_id} not found")
    if response.status_code >= 500:
        raise UserServiceError(503, f"User service returned {response.status_code}")

    try:
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise UserServiceError(503, f"User service returned an invalid response: {exc}") from exc

    return UserLookup(payload, elapsed_ms)
