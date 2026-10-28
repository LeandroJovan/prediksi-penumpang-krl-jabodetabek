from fastapi import APIRouter, Request
from sqlalchemy import text

router = APIRouter(tags=["health"])


@router.get("/health/live")
async def live() -> dict:
    return {"status": "ok"}


@router.get("/health/ready")
async def ready(request: Request) -> dict:
    async with request.app.state.session_factory() as session:
        await session.execute(text("SELECT 1"))
    await request.app.state.redis.ping()
    return {"status": "ready"}
