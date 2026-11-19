import logging
import secrets
import time
from collections import deque

from fastapi import Header, HTTPException, Request, status

from backend.app.core.config import get_settings

logger = logging.getLogger("krl_backend.security")


PLACEHOLDER_API_KEYS = frozenset({"replace-with-a-long-random-secret", "change-me", "changeme", "secret", "admin"})
MIN_API_KEY_LENGTH = 16
ADMIN_MAX_FAILURES_PER_MINUTE = 10


def admin_key_is_usable(key: str | None) -> bool:
    """Kunci admin hanya dianggap terkonfigurasi jika cukup panjang dan bukan placeholder dari template."""
    return bool(key) and len(key) >= MIN_API_KEY_LENGTH and key.lower() not in PLACEHOLDER_API_KEYS


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


async def require_admin_api_key(request: Request, x_api_key: str | None = Header(default=None)) -> None:
    """Autentikasi admin lewat header ``X-API-Key``.

    - Fail-closed: tanpa KRL_API_KEY yang layak, seluruh endpoint admin nonaktif (503), bukan terbuka.
    - Perbandingan constant-time pada bytes (``compare_digest`` pada str non-ASCII akan melempar TypeError).
    - Percobaan gagal dibatasi per IP agar kunci tidak bisa ditebak lewat brute force.
    """
    expected = get_settings().krl_api_key
    if not admin_key_is_usable(expected):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin API is disabled: set KRL_API_KEY (min 16 karakter, bukan placeholder).",
        )

    ip = _client_ip(request)
    blocked = _auth_failures.blocked(ip, ADMIN_MAX_FAILURES_PER_MINUTE)
    if blocked is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed attempts",
            headers={"Retry-After": str(int(blocked))},
        )
    if not x_api_key or not secrets.compare_digest(expected.encode(), x_api_key.encode()):
        _auth_failures.check(ip, ADMIN_MAX_FAILURES_PER_MINUTE)
        logger.warning("Admin auth gagal dari %s untuk %s", ip, request.url.path)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )


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

    def blocked(self, key: str, limit: int, now: float | None = None) -> float | None:
        """Cek tanpa mencatat hit: detik tunggu jika ``key`` sudah mencapai ``limit``, selain itu None."""
        if limit <= 0:
            return None
        now = time.monotonic() if now is None else now
        hits = self._hits.get(key)
        if not hits:
            return None
        while hits and now - hits[0] >= self.window:
            hits.popleft()
        if len(hits) >= limit:
            return max(self.window - (now - hits[0]), 1.0)
        return None

    def _evict(self, now: float) -> None:
        stale = [k for k, h in self._hits.items() if not h or now - h[-1] >= self.window]
        for k in stale:
            del self._hits[k]
        while len(self._hits) > self.max_keys:
            del self._hits[next(iter(self._hits))]


_limiter = SlidingWindowLimiter()
_auth_failures = SlidingWindowLimiter()


async def rate_limit(request: Request) -> None:
    """Dependency FastAPI: batasi endpoint mahal per IP klien."""
    limit = get_settings().rate_limit_per_minute
    client = _client_ip(request)
    retry_after = _limiter.check(f"{request.url.path}:{client}", limit)
    if retry_after is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests",
            headers={"Retry-After": str(int(retry_after))},
        )
