from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import db_session, redis_client, settings
from backend.app.core.config import REPO_ROOT, Settings
from backend.app.core.pipeline_data import read_csv_async
from backend.app.core.security import rate_limit
from backend.app.schemas.forecast import ForecastResponse
from backend.app.services.forecast import ForecastService

ROOT = REPO_ROOT
router = APIRouter(prefix="/risk", tags=["risk"])


class RiskSimulationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capacity_weekday_ribu: float | None = Field(default=None, gt=0, le=1_000_000, allow_inf_nan=False)
    capacity_weekend_ribu: float | None = Field(default=None, gt=0, le=1_000_000, allow_inf_nan=False)
    ambang_kapasitas: float | None = Field(default=None, gt=0, le=1_000_000, allow_inf_nan=False)
    batas_waspada: float = Field(default=0.90, gt=0, lt=1, allow_inf_nan=False)
    kolom_batas_atas: Literal["batas_atas_80", "batas_atas_95"] = "batas_atas_95"
    horizons: list[Annotated[int, Field(ge=1, le=24)]] | None = Field(default=None, max_length=24)


@router.get("/latest", response_model=ForecastResponse)
async def latest_risk(
    session: AsyncSession = Depends(db_session),
    app_settings: Settings = Depends(settings),
    redis=Depends(redis_client),
) -> ForecastResponse:
    """Mengambil status risiko kapasitas terkini untuk seluruh horizon."""
    return await ForecastService(session, app_settings, redis).latest()


@router.post("/simulate", response_model=ForecastResponse, dependencies=[Depends(rate_limit)])
async def simulate_risk(
    payload: RiskSimulationRequest,
    session: AsyncSession = Depends(db_session),
    app_settings: Settings = Depends(settings),
    redis=Depends(redis_client),
) -> ForecastResponse:
    """Simulasi reaktif status risiko kapasitas dengan ambang atau interval custom."""
    basis = "80" if payload.kolom_batas_atas == "batas_atas_80" else "95"
    update_dict = {"krl_risk_waspada_ratio": payload.batas_waspada}
    if payload.capacity_weekday_ribu is not None:
        update_dict["krl_capacity_weekday_ribu"] = payload.capacity_weekday_ribu
    if payload.capacity_weekend_ribu is not None:
        update_dict["krl_capacity_weekend_ribu"] = payload.capacity_weekend_ribu

    simulated_settings = app_settings.model_copy(update=update_dict)
    return await ForecastService(session, simulated_settings, redis).latest(
        horizons=payload.horizons,
        capacity_monthly=payload.ambang_kapasitas,
        waspada_ratio=payload.batas_waspada,
        basis_col=basis,
    )


@router.get("/sensitivity")
async def get_sensitivity() -> dict:
    """Mengambil tabel analisis sensitivitas pergeseran kapasitas (-10% s.d. +10%)."""
    path_file = ROOT / "outputs/analisis_sensitivitas_kapasitas.csv"
    if path_file.exists():
        df = await read_csv_async(path_file)
        return {"data": df.to_dict(orient="records")}
    return {"data": []}
