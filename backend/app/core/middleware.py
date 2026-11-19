import re
import time
import uuid

from fastapi import Request

# Hanya karakter aman; mencegah log injection / header injection dari klien.
_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def _resolve_request_id(candidate: str | None) -> str:
    if candidate and _REQUEST_ID_RE.fullmatch(candidate):
        return candidate
    return str(uuid.uuid4())


async def request_id_middleware(request: Request, call_next):
    request.state.request_id = _resolve_request_id(request.headers.get("X-Request-ID"))
    started = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    response.headers["X-Response-Time-Ms"] = str(round((time.perf_counter() - started) * 1000, 2))
    return response
