import uuid

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status

from app.auth import require_token
from app.models import ErrorResponse, User, UserIn
from app.storage import DuplicateEmailError, storage

API_PREFIX = "/api/v1"

app = FastAPI(
    title="Users API",
    version="1.0.0",
    contact={"name": "sssiqwel"},
    description=(
        "Сервис управления пользователями.\n\n"
        "Чтение (`GET`) доступно всем. Создание требует заголовка "
        "`Authorization: Bearer <token>` — нажмите **Authorize** и введите `secret-token`."
    ),
    openapi_tags=[
        {"name": "users", "description": "Создание и получение пользователей"},
        {"name": "service", "description": "Служебные эндпоинты"},
    ],
)

NOT_FOUND = {404: {"model": ErrorResponse, "description": "Пользователь не найден"}}
UNAUTHORIZED = {401: {"model": ErrorResponse, "description": "Нет токена или токен неверный"}}
CONFLICT = {409: {"model": ErrorResponse, "description": "Пользователь с таким email уже есть"}}


@app.middleware("http")
async def request_id_header(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


def get_user_or_404(user_id: int) -> User:
    user = storage.get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    return user


@app.get("/health", tags=["service"], summary="Проверка, что сервер жив")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get(f"{API_PREFIX}/users", tags=["users"], summary="Список пользователей")
def list_users() -> list[User]:
    return storage.list()


@app.get(f"{API_PREFIX}/users/{{user_id}}", tags=["users"], summary="Пользователь по id", responses=NOT_FOUND)
def get_user(user_id: int) -> User:
    return get_user_or_404(user_id)


@app.post(
    f"{API_PREFIX}/users",
    tags=["users"],
    summary="Создать пользователя",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_token)],
    responses={**UNAUTHORIZED, **CONFLICT},
)
def create_user(data: UserIn, response: Response) -> User:
    try:
        user = storage.create(data)
    except DuplicateEmailError:
        raise HTTPException(status_code=409, detail=f"User with email {data.email} already exists")
    response.headers["Location"] = f"{API_PREFIX}/users/{user.id}"
    return user
