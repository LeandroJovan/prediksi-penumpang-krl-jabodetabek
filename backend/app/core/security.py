import secrets
import time
from collections import deque

from fastapi import Header, HTTPException, Request, status

from backend.app.core.config import get_settings


async def require_admin_api_key(x_api_key: str | None = Header(default=None)) -> None:
    expected = get_settings().krl_api_key
    if not expected or not x_api_key or not secrets.compare_digest(expected, x_api_key):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")


class SlidingWindowLimiter:
    """Pembatas laju sliding-window in-memory per kunci (mis. IP klien)."""

    def __init__(self, window_seconds: float = 60.0, max_keys: int = 10_000) -> None:
        self.window = window_seconds
        self.max_keys = max_keys
        self._hits: dict[str, deque[float]] = {}

    def check(self, key: str, limit: int, now: float | None = None) -> float | None:
        """Catat satu hit. Return None jika diizinkan, atau detik tunggu (Retry-After) jika ditolak."""
        if limit <= 0:
            return None
        now = time.monotonic() if now is None else now
        hits = self._hits.setdefault(key, deque())
        while hits and now - hits[0] >= self.window:
            hits.popleft()
        if len(hits) >= limit:
            return max(self.window - (now - hits[0]), 1.0)
        hits.append(now)
        if len(self._hits) > self.max_keys:
            self._evict(now)
        return None

    def _evict(self, now: float) -> None:
        stale = [k for k, h in self._hits.items() if not h or now - h[-1] >= self.window]
        for k in stale:
            del self._hits[k]
        while len(self._hits) > self.max_keys:
            del self._hits[next(iter(self._hits))]


_limiter = SlidingWindowLimiter()


async def rate_limit(request: Request) -> None:
    """Dependency FastAPI: batasi endpoint mahal per IP klien."""
    limit = get_settings().rate_limit_per_minute
    client = request.client.host if request.client else "unknown"
    retry_after = _limiter.check(f"{request.url.path}:{client}", limit)
    if retry_after is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests",
            headers={"Retry-After": str(int(retry_after))},
        )
