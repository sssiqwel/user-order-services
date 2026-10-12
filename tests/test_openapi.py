import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_exported_users_openapi_is_up_to_date(users_api):
    live = users_api.get("/openapi.json").json()
    exported = json.loads((ROOT / "openapi" / "users.json").read_text(encoding="utf-8"))
    assert live == exported


def test_exported_orders_openapi_is_up_to_date(orders_api):
    live = orders_api.get("/openapi.json").json()
    exported = json.loads((ROOT / "openapi" / "orders.json").read_text(encoding="utf-8"))
    assert live == exported
