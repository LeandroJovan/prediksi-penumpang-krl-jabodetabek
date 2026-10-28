from typing import Literal

from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import db_session, redis_client, settings
from backend.app.core.config import Settings
from backend.app.schemas.insight import InsightResponse
from backend.app.services.forecast import ForecastService
from backend.app.services.insights import InsightService

router = APIRouter(prefix="/insights", tags=["insights"])


@router.get("/latest", response_model=InsightResponse)
async def latest_insight(
    language: Literal["id", "en"] = "id", session: AsyncSession = Depends(db_session),
    app_settings: Settings = Depends(settings), redis: Redis = Depends(redis_client),
) -> InsightResponse:
    forecast = await ForecastService(session, app_settings, redis).latest()
    return await InsightService(redis, app_settings).generate(forecast, language)
