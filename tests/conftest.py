import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

import pytest
import requests

ROOT = Path(__file__).resolve().parent.parent
HOST = os.getenv("HOST", "127.0.0.1")
USERS_PORT = os.getenv("USERS_PORT", "8001")
ORDERS_PORT = os.getenv("ORDERS_PORT", "8002")
USERS_URL = os.getenv("USERS_URL", f"http://{HOST}:{USERS_PORT}")
ORDERS_URL = os.getenv("ORDERS_URL", f"http://{HOST}:{ORDERS_PORT}")
API_TOKEN = os.getenv("API_TOKEN", "secret-token")
USER_FETCH_SLO_MS = float(os.getenv("USER_FETCH_SLO_MS", "500"))


class ApiClient(requests.Session):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url.rstrip("/")
        self.headers["Accept"] = "application/json"

    def request(self, method, url, *args, **kwargs):
        kwargs.setdefault("timeout", 5)
        return super().request(method, f"{self.base_url}{url}", *args, **kwargs)


def _is_up(url: str) -> bool:
    try:
        return requests.get(f"{url}/health", timeout=0.5).status_code == 200
    except requests.RequestException:
        return False


def _start_service(cwd: Path, port: str, extra_env: dict[str, str] | None = None) -> subprocess.Popen:
    env = os.environ.copy()
    env["API_TOKEN"] = API_TOKEN
    if extra_env:
        env.update(extra_env)
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", HOST, "--port", port],
        cwd=cwd,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )
    url = f"http://{HOST}:{port}"
    for _ in range(50):
        if _is_up(url):
            return proc
        if proc.poll() is not None:
            pytest.exit(f"Server in {cwd.name} exited with code {proc.returncode}", returncode=1)
        time.sleep(0.2)
    proc.terminate()
    proc.wait(timeout=5)
    pytest.exit(f"Server in {cwd.name} did not start at {url}", returncode=1)


def _stop(proc: subprocess.Popen | None) -> None:
    if proc is None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


@pytest.fixture(scope="session")
def users_url():
    if _is_up(USERS_URL):
        yield USERS_URL
        return

    proc = _start_service(ROOT / "users_service", USERS_PORT)
    try:
        yield USERS_URL
    finally:
        _stop(proc)


@pytest.fixture(scope="session")
def orders_url(users_url):
    if _is_up(ORDERS_URL):
        yield ORDERS_URL
        return

    proc = _start_service(
        ROOT / "orders_service",
        ORDERS_PORT,
        extra_env={"USER_SERVICE_URL": users_url, "USER_SERVICE_TIMEOUT": "2"},
    )
    try:
        yield ORDERS_URL
    finally:
        _stop(proc)


@pytest.fixture
def users_api(users_url):
    with ApiClient(users_url) as client:
        yield client


@pytest.fixture
def orders_api(orders_url):
    with ApiClient(orders_url) as client:
        yield client


@pytest.fixture
def auth_headers():
    return {"Authorization": f"Bearer {API_TOKEN}"}


@pytest.fixture
def user_payload():
    return {
        "name": "Иван Тестировщиков",
        "email": f"user-{uuid.uuid4().hex[:8]}@example.com",
    }


@pytest.fixture
def created_user(users_api, auth_headers, user_payload):
    response = users_api.post("/api/v1/users", json=user_payload, headers=auth_headers)
    assert response.status_code == 201, response.text
    yield response.json()


@pytest.fixture
def order_payload(created_user):
    return {
        "user_id": created_user["id"],
        "item": "Настольная лампа",
        "quantity": 2,
    }


@pytest.fixture
def created_order(orders_api, auth_headers, order_payload, created_user):
    response = orders_api.post("/api/v1/orders", json=order_payload, headers=auth_headers)
    assert response.status_code == 201, response.text
    yield response.json()


@pytest.fixture
def isolated_orders_api():
    """Orders API, который смотрит на заведомо мёртвый Users API."""
    port = os.getenv("ISOLATED_ORDERS_PORT", "18002")
    proc = _start_service(
        ROOT / "orders_service",
        port,
        extra_env={
            "USER_SERVICE_URL": "http://127.0.0.1:9",
            "USER_SERVICE_TIMEOUT": "0.3",
        },
    )
    try:
        with ApiClient(f"http://{HOST}:{port}") as client:
            yield client
    finally:
        _stop(proc)
