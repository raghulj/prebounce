"""Built-in caches."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any


class MemoryCache:
    """In-process Cache with per-key expiry. Not shared across processes."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._data: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        entry = self._data.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if self._clock() >= expires_at:
            del self._data[key]
            return None
        return value

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        if ttl_seconds <= 0:
            self._data.pop(key, None)
            return
        self._data[key] = (self._clock() + ttl_seconds, value)

    def __len__(self) -> int:
        return len(self._data)
