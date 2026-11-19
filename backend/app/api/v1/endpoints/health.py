import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

logger = logging.getLogger("krl_backend.health")
router = APIRouter(tags=["health"])


@router.get("/health")
@router.get("/health/live")
async def live() -> dict:
    return {
        "status": "healthy",
        "service": "KRL Ridership Forecasting & Capacity Risk FastAPI",
        "version": "1.0.0",
    }


@router.get("/health/ready")
async def ready(request: Request):
    """Readiness: 200 jika DB dan cache terjangkau, 503 (tanpa detail internal) jika tidak."""
    checks: dict[str, str] = {}

    try:
        async with request.app.state.session_factory() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        logger.exception("Readiness: database tidak dapat dijangkau")
        checks["database"] = "unavailable"

    cache = getattr(request.app.state, "redis", None)
    if cache is not None and hasattr(cache, "ping"):
        try:
            await cache.ping()
            checks["cache"] = "ok"
        except Exception:
            logger.exception("Readiness: cache tidak dapat dijangkau")
            checks["cache"] = "unavailable"

    if all(value == "ok" for value in checks.values()):
        return {"status": "ready", "checks": checks}
    return JSONResponse(status_code=503, content={"status": "not_ready", "checks": checks})
