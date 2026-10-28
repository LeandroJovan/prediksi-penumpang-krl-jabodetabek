from datetime import date

from pydantic import BaseModel, Field

from backend.app.schemas.common import Interval


class RiskResult(BaseModel):
    status: str
    utilization: float | None = None
    capacity_ribu: float | None = None
    basis: str = "upper95"
    reason: str | None = None


class ForecastItem(BaseModel):
    period: date
    horizon: int = Field(ge=1)
    point: float
    intervals: dict[str, Interval]
    risk: RiskResult


class ForecastResponse(BaseModel):
    data: list[ForecastItem]
    meta: dict
