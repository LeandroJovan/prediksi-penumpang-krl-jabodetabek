import asyncio
import time
from collections import OrderedDict

DEFAULT_MAX_ENTRIES = 1000


class InMemoryCache:
    """
    In-memory async cache with TTL support and a bounded size (LRU eviction).
    Used as an automatic zero-config fallback when Redis is not running.

    Batas ukuran mencegah memori membengkak jika kunci cache dibentuk dari
    input pengguna (mis. nilai ambang kapasitas yang berbeda-beda).
    """

    def __init__(self, max_entries: int = DEFAULT_MAX_ENTRIES) -> None:
        if max_entries < 1:
            raise ValueError("max_entries must be >= 1")
        self._max_entries = max_entries
        self._store: OrderedDict[str, tuple[str, float | None]] = OrderedDict()
        self._lock = asyncio.Lock()

    def _purge_expired(self, now: float) -> None:
        expired = [k for k, (_, exp) in self._store.items() if exp is not None and now > exp]
        for key in expired:
            del self._store[key]

    async def get(self, key: str) -> str | None:
        async with self._lock:
            if key not in self._store:
                return None
            val, expiry = self._store[key]
            if expiry is not None and time.time() > expiry:
                del self._store[key]
                return None
            self._store.move_to_end(key)
            return val

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        async with self._lock:
            now = time.time()
            expiry = now + ex if ex is not None else None
            self._store[key] = (value, expiry)
            self._store.move_to_end(key)
            if len(self._store) > self._max_entries:
                self._purge_expired(now)
            while len(self._store) > self._max_entries:
                self._store.popitem(last=False)

    async def delete(self, key: str) -> None:
        async with self._lock:
            self._store.pop(key, None)

    async def delete_prefix(self, prefix: str) -> int:
        async with self._lock:
            keys = [k for k in self._store if k.startswith(prefix)]
            for key in keys:
                del self._store[key]
            return len(keys)

    async def ping(self) -> bool:
        return True

    async def aclose(self) -> None:
        async with self._lock:
            self._store.clear()
