from fastapi import APIRouter, Depends, Query
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import db_session, redis_client, settings
from backend.app.core.config import Settings
from backend.app.schemas.forecast import ForecastResponse
from backend.app.services.forecast import ForecastService

router = APIRouter(prefix="/forecasts", tags=["forecasts"])


@router.get("/latest", response_model=ForecastResponse)
async def latest_forecast(
    horizon: list[int] | None = Query(default=None),
    session: AsyncSession = Depends(db_session),
    app_settings: Settings = Depends(settings),
    redis: Redis = Depends(redis_client),
) -> ForecastResponse:
    return await ForecastService(session, app_settings, redis).latest(horizon)
