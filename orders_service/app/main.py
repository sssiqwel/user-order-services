import uuid

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status

from app.auth import require_token
from app.models import ErrorResponse, Order, OrderIn, UserSnapshot
from app.storage import StoredOrder, storage
from app.users_client import UserServiceError, get_user

API_PREFIX = "/api/v1"

app = FastAPI(
    title="Orders API",
    version="1.0.0",
    contact={"name": "sssiqwel"},
    description=(
        "Сервис управления заказами.\n\n"
        "При создании и чтении заказа сервис запрашивает пользователя "
        "в Users API по `user_id`. Если Users API недоступен, возвращается `503`.\n\n"
        "Создание требует заголовка `Authorization: Bearer <token>` — "
        "нажмите **Authorize** и введите `secret-token`."
    ),
    openapi_tags=[
        {"name": "orders", "description": "Создание и получение заказов"},
        {"name": "service", "description": "Служебные эндпоинты"},
    ],
)

NOT_FOUND = {404: {"model": ErrorResponse, "description": "Заказ или пользователь не найден"}}
UNAUTHORIZED = {401: {"model": ErrorResponse, "description": "Нет токена или токен неверный"}}
UNAVAILABLE = {503: {"model": ErrorResponse, "description": "Users API недоступен"}}


@app.middleware("http")
async def request_id_header(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


def enrich_order(stored: StoredOrder, request_id: str | None) -> tuple[Order, float]:
    try:
        lookup = get_user(stored.user_id, request_id=request_id)
    except UserServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    order = Order(
        id=stored.id,
        user_id=stored.user_id,
        item=stored.item,
        quantity=stored.quantity,
        user=UserSnapshot.model_validate(lookup.user),
    )
    return order, lookup.elapsed_ms


def attach_timing(response: Response, elapsed_ms: float) -> None:
    response.headers["X-User-Service-Time-Ms"] = f"{elapsed_ms:.2f}"


@app.get("/health", tags=["service"], summary="Проверка, что сервер жив")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get(
    f"{API_PREFIX}/orders",
    tags=["orders"],
    summary="Список заказов",
    responses={**NOT_FOUND, **UNAVAILABLE},
)
def list_orders(request: Request, response: Response) -> list[Order]:
    orders: list[Order] = []
    total_ms = 0.0
    for stored in storage.list():
        order, elapsed_ms = enrich_order(stored, getattr(request.state, "request_id", None))
        orders.append(order)
        total_ms += elapsed_ms
    attach_timing(response, total_ms)
    return orders


@app.get(
    f"{API_PREFIX}/orders/{{order_id}}",
    tags=["orders"],
    summary="Заказ по id (с данными пользователя)",
    responses={**NOT_FOUND, **UNAVAILABLE},
)
def get_order(order_id: int, request: Request, response: Response) -> Order:
    stored = storage.get(order_id)
    if stored is None:
        raise HTTPException(status_code=404, detail=f"Order {order_id} not found")
    order, elapsed_ms = enrich_order(stored, getattr(request.state, "request_id", None))
    attach_timing(response, elapsed_ms)
    return order


@app.post(
    f"{API_PREFIX}/orders",
    tags=["orders"],
    summary="Создать заказ (проверяет пользователя в Users API)",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_token)],
    responses={**UNAUTHORIZED, **NOT_FOUND, **UNAVAILABLE},
)
def create_order(data: OrderIn, request: Request, response: Response) -> Order:
    try:
        lookup = get_user(data.user_id, request_id=getattr(request.state, "request_id", None))
    except UserServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    stored = storage.create(data)
    order = Order(
        id=stored.id,
        user_id=stored.user_id,
        item=stored.item,
        quantity=stored.quantity,
        user=UserSnapshot.model_validate(lookup.user),
    )
    response.headers["Location"] = f"{API_PREFIX}/orders/{order.id}"
    attach_timing(response, lookup.elapsed_ms)
    return order
