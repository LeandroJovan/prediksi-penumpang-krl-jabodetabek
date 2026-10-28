from datetime import date

from backend.app.core.config import Settings
from backend.app.schemas.forecast import RiskResult


def calculate_risk(upper95: float, calendar: dict, settings: Settings) -> RiskResult:
    weekday = settings.krl_capacity_weekday_ribu
    weekend = settings.krl_capacity_weekend_ribu
    if weekday is None or weekend is None:
        return RiskResult(status="belum_ditentukan", reason="capacity_not_configured")
    non_workdays = calendar["total_hari"] - calendar["jumlah_hari_kerja"]
    capacity = weekday * calendar["jumlah_hari_kerja"] + weekend * non_workdays
    utilization = upper95 / capacity
    if utilization >= 1:
        status = "kritis"
    elif utilization >= settings.krl_risk_waspada_ratio:
        status = "waspada"
    else:
        status = "aman"
    return RiskResult(status=status, utilization=round(utilization, 4), capacity_ribu=capacity)
