from __future__ import annotations

from collections.abc import Iterable
from threading import Lock

from app.models.sandbox import SandboxRecord


class SandboxRegistry:
    def __init__(self) -> None:
        self._items: dict[str, SandboxRecord] = {}
        self._lock = Lock()

    def put(self, sandbox: SandboxRecord) -> SandboxRecord:
        with self._lock:
            self._items[sandbox.id] = sandbox
        return sandbox

    def get(self, sandbox_id: str) -> SandboxRecord | None:
        with self._lock:
            return self._items.get(sandbox_id)

    def delete(self, sandbox_id: str) -> SandboxRecord | None:
        with self._lock:
            return self._items.pop(sandbox_id, None)

    def all(self) -> Iterable[SandboxRecord]:
        with self._lock:
            return tuple(self._items.values())


registry = SandboxRegistry()

