from fastapi import Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import Settings, get_settings
from backend.app.db.session import get_session


async def db_session() -> AsyncSession:
    async for session in get_session():
        yield session


def settings() -> Settings:
    return get_settings()


def redis_client(request: Request) -> Redis:
    return request.app.state.redis
