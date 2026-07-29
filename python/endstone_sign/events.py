from __future__ import annotations

from collections.abc import Callable
from threading import RLock

from .model import SignEvent


SignEventListener = Callable[[SignEvent], None]


class SignEventBus:
    def __init__(self) -> None:
        self._lock = RLock()
        self._listeners: dict[int, SignEventListener] = {}
        self._next_id = 1

    def add_listener(self, listener: SignEventListener) -> int:
        if not callable(listener):
            raise TypeError("sign event listener must be callable")
        with self._lock:
            listener_id = self._next_id
            self._next_id += 1
            self._listeners[listener_id] = listener
            return listener_id

    def remove_listener(self, listener_id: int) -> bool:
        with self._lock:
            return self._listeners.pop(listener_id, None) is not None

    def publish(self, event: SignEvent) -> None:
        with self._lock:
            listeners = tuple(self._listeners.values())
        for listener in listeners:
            listener(event)
            if event.cancellable and event.cancelled:
                break
