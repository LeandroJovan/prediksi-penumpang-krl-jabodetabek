from fastapi import APIRouter, Request
from sqlalchemy import text

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
async def ready(request: Request) -> dict:
    async with request.app.state.session_factory() as session:
        await session.execute(text("SELECT 1"))
    if hasattr(request.app.state, "redis") and hasattr(request.app.state.redis, "ping"):
        await request.app.state.redis.ping()
    return {"status": "ready"}
