from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import db_session, redis_client, settings
from backend.app.core.config import Settings
from backend.app.schemas.forecast import ForecastResponse
from backend.app.services.forecast import ForecastService

router = APIRouter(prefix="/risk", tags=["risk"])


class RiskSimulationRequest(BaseModel):
    capacity_weekday_ribu: float = Field(gt=0)
    capacity_weekend_ribu: float = Field(gt=0)
    horizons: list[int] | None = None


@router.get("/latest")
async def latest_risk(session: AsyncSession = Depends(db_session), app_settings: Settings = Depends(settings), redis: Redis = Depends(redis_client)) -> ForecastResponse:
    return await ForecastService(session, app_settings, redis).latest()


@router.post("/simulate")
async def simulate_risk(payload: RiskSimulationRequest, session: AsyncSession = Depends(db_session), app_settings: Settings = Depends(settings), redis: Redis = Depends(redis_client)) -> ForecastResponse:
    simulated = app_settings.model_copy(update={"krl_capacity_weekday_ribu": payload.capacity_weekday_ribu,
                                                 "krl_capacity_weekend_ribu": payload.capacity_weekend_ribu})
    return await ForecastService(session, simulated, redis).latest(payload.horizons)
