from datetime import date

from backend.app.core.config import Settings
from backend.app.schemas.forecast import RiskResult


def calculate_risk(
    upper_val: float,
    calendar: dict,
    settings: Settings,
    capacity_monthly_override: float | None = None,
    waspada_ratio_override: float | None = None,
) -> RiskResult:
    """
    Kalkulasi status risiko operasional kapasitas KRL:
    - Aman: utilization < waspada_ratio (default < 90%)
    - Waspada: waspada_ratio <= utilization < 100%
    - Kritis: utilization >= 100%
    """
    waspada_ratio = waspada_ratio_override if waspada_ratio_override is not None else settings.krl_risk_waspada_ratio

    if capacity_monthly_override is not None:
        capacity = float(capacity_monthly_override)
    else:
        weekday = settings.krl_capacity_weekday_ribu
        weekend = settings.krl_capacity_weekend_ribu
        if weekday is None or weekend is None:
            return RiskResult(status="belum_ditentukan", reason="capacity_not_configured")
        non_workdays = calendar.get("total_hari", 30) - calendar.get("jumlah_hari_kerja", 20)
        capacity = weekday * calendar.get("jumlah_hari_kerja", 20) + weekend * non_workdays

    utilization = upper_val / capacity if capacity > 0 else 0.0
    if utilization >= 1.0:
        status = "kritis"
    elif utilization >= waspada_ratio:
        status = "waspada"
    else:
        status = "aman"

    return RiskResult(
        status=status,
        utilization=round(utilization, 4),
        capacity_ribu=round(capacity, 1),
    )
