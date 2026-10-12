from threading import Lock

from app.models import OrderIn


class StoredOrder:
    def __init__(self, order_id: int, data: OrderIn) -> None:
        self.id = order_id
        self.user_id = data.user_id
        self.item = data.item
        self.quantity = data.quantity


class OrderStorage:
    """Хранилище в памяти. Данные живут, пока запущен процесс сервера."""

    def __init__(self) -> None:
        self._lock = Lock()
        self.reset()

    def reset(self) -> None:
        with self._lock:
            self._orders: dict[int, StoredOrder] = {}
            self._next_id = 1

    def list(self) -> list[StoredOrder]:
        return list(self._orders.values())

    def get(self, order_id: int) -> StoredOrder | None:
        return self._orders.get(order_id)

    def create(self, data: OrderIn) -> StoredOrder:
        with self._lock:
            order = StoredOrder(self._next_id, data)
            self._orders[order.id] = order
            self._next_id += 1
            return order


storage = OrderStorage()
