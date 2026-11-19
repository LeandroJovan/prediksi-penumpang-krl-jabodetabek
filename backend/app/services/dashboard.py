"""Bundle dashboard: prakiraan dari ForecastService (model aktif), bukan dari CSV mentah.

Bagian historis dan evaluasi berasal dari artefak pipeline (CSV); bagian prakiraan, label model, dan
kapasitas mengikuti backend sehingga dashboard, chat, dan insight memakai angka yang sama.
"""
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import Settings
from backend.app.services.forecast import ForecastService


class DashboardService:
    def __init__(self, session: AsyncSession, settings: Settings, redis) -> None:
        self.session, self.settings, self.redis = session, settings, redis

    async def bundle(self, ambang_kapasitas: float | None = None) -> dict:
        from backend.api import build_dashboard_bundle  # import lambat: memuat modul Flask lama

        forecast = await ForecastService(self.session, self.settings, self.redis).latest(
            capacity_monthly=ambang_kapasitas
        )
        capacity = forecast.meta.get("ambang_kapasitas_aktif") or self.settings.krl_capacity_monthly_ribu
        data = await run_in_threadpool(build_dashboard_bundle, capacity)

        data["forecast"] = [
            {
                "bulan": item.period.strftime("%Y-%m"),
                "horizon": item.horizon,
                "titik": item.point,
                "l80": item.intervals["80"].lower,
                "u80": item.intervals["80"].upper,
                "l95": item.intervals["95"].lower,
                "u95": item.intervals["95"].upper,
                "status": item.risk.status,
            }
            for item in forecast.data
        ]
        data["meta"].update(
            {
                "model_terpilih": forecast.meta.get("algorithm"),
                "model_run_id": forecast.meta.get("model_run_id"),
                "sumber_forecast": forecast.meta.get("source", "csv_pipeline"),
                "data_through": forecast.meta.get("data_through"),
            }
        )
        data["ambang_kapasitas"]["nilai"] = float(capacity)
        return data
