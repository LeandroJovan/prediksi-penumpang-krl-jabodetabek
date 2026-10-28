from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    def __init__(self, code: str, status_code: int, detail: str) -> None:
        self.code = code
        self.status_code = status_code
        self.detail = detail


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    body: dict[str, Any] = {
        "type": f"https://krl-forecast.local/errors/{exc.code.lower().replace('_', '-')}",
        "title": exc.code.replace("_", " ").title(),
        "status": exc.status_code,
        "detail": exc.detail,
        "instance": request.url.path,
        "request_id": request_id,
    }
    return JSONResponse(status_code=exc.status_code, content=body)
