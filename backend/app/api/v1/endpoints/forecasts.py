from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import db_session, redis_client, settings
from backend.app.core.config import Settings
from backend.app.schemas.forecast import ForecastResponse
from backend.app.services.forecast import ForecastService

router = APIRouter(prefix="/forecasts", tags=["forecasts"])


@router.get("/latest", response_model=ForecastResponse)
async def latest_forecast(
    horizon: list[int] | None = Query(default=None, description="Filter horizon bulan (1-6)"),
    ambang_kapasitas: float | None = Query(default=None, description="Ambang kapasitas bulanan dalam ribu orang"),
    batas_waspada: float | None = Query(default=None, description="Rasio batas waspada (default 0.90)"),
    basis_interval: str = Query(default="95", pattern="^(80|95)$", description="Basis interval ketidakpastian"),
    session: AsyncSession = Depends(db_session),
    app_settings: Settings = Depends(settings),
    redis=Depends(redis_client),
) -> ForecastResponse:
    """Mengambil prakiraan 6 bulan ke depan dengan interval ketidakpastian dan status risiko."""
    return await ForecastService(session, app_settings, redis).latest(
        horizons=horizon,
        capacity_monthly=ambang_kapasitas,
        waspada_ratio=batas_waspada,
        basis_col=basis_interval,
    )
