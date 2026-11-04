import asyncio
import time
from typing import Any


class InMemoryCache:
    """
    In-memory async cache with TTL support.
    Used as an automatic zero-config fallback when Redis is not running.
    """

    def __init__(self) -> None:
        self._store: dict[str, tuple[str, float | None]] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> str | None:
        async with self._lock:
            if key not in self._store:
                return None
            val, expiry = self._store[key]
            if expiry is not None and time.time() > expiry:
                del self._store[key]
                return None
            return val

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        async with self._lock:
            expiry = time.time() + ex if ex is not None else None
            self._store[key] = (value, expiry)

    async def delete(self, key: str) -> None:
        async with self._lock:
            self._store.pop(key, None)

    async def ping(self) -> bool:
        return True

    async def aclose(self) -> None:
        async with self._lock:
            self._store.clear()

