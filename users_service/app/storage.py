from threading import Lock

from app.models import User, UserIn

SEED_USERS = [
    UserIn(name="Анна Иванова", email="anna@example.com"),
    UserIn(name="Пётр Петров", email="petr@example.com"),
]


class DuplicateEmailError(Exception):
    pass


class UserStorage:
    """Хранилище в памяти. Данные живут, пока запущен процесс сервера."""

    def __init__(self) -> None:
        self._lock = Lock()
        self.reset()

    def reset(self) -> None:
        with self._lock:
            self._users: dict[int, User] = {}
            self._next_id = 1
        for user in SEED_USERS:
            self.create(user)

    def list(self) -> list[User]:
        return list(self._users.values())

    def get(self, user_id: int) -> User | None:
        return self._users.get(user_id)

    def create(self, data: UserIn) -> User:
        with self._lock:
            self._ensure_email_free(data.email)
            user = User(id=self._next_id, **data.model_dump())
            self._users[user.id] = user
            self._next_id += 1
            return user

    def _ensure_email_free(self, email: str) -> None:
        for user in self._users.values():
            if user.email == email:
                raise DuplicateEmailError(email)


storage = UserStorage()
