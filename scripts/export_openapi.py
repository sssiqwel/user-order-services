import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_openapi(service_dir: Path) -> dict:
    for name in list(sys.modules):
        if name == "app" or name.startswith("app."):
            del sys.modules[name]
    sys.path.insert(0, str(service_dir))
    try:
        from app.main import app

        return app.openapi()
    finally:
        sys.path.pop(0)
        for name in list(sys.modules):
            if name == "app" or name.startswith("app."):
                del sys.modules[name]


def dump(spec: dict, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {dest.relative_to(ROOT)}")


def main() -> None:
    dump(load_openapi(ROOT / "users_service"), ROOT / "openapi" / "users.json")
    dump(load_openapi(ROOT / "orders_service"), ROOT / "openapi" / "orders.json")


if __name__ == "__main__":
    main()
