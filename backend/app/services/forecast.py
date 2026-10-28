import asyncio
from datetime import date

import pandas as pd
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import Settings
from backend.app.core.errors import AppError
from backend.app.db.models import Actual, Calendar, ModelRun
from backend.app.ml.loader import load_bundle
from backend.app.ml.validation import validate_forecast
from backend.app.schemas.forecast import ForecastItem, ForecastResponse, Interval
from backend.app.services.risk import calculate_risk


class ForecastService:
    def __init__(self, session: AsyncSession, settings: Settings, redis) -> None:
        self.session, self.settings, self.redis = session, settings, redis

    async def latest(self, horizons: list[int] | None = None) -> ForecastResponse:
        model_run = await self._active_model()
        requested = horizons or list(range(1, model_run.horizon_max + 1))
        if any(h < 1 or h > model_run.horizon_max for h in requested):
            raise AppError("HORIZON_NOT_AVAILABLE", 422, "Requested horizon is not available.")
        capacity_key = f"{self.settings.krl_capacity_weekday_ribu}:{self.settings.krl_capacity_weekend_ribu}:{self.settings.krl_risk_waspada_ratio}"
        cache_key = f"forecast:v1:{model_run.run_id}:{','.join(map(str, requested))}:{capacity_key}"
        cached = await self.redis.get(cache_key)
        if cached:
            return ForecastResponse.model_validate_json(cached)
        history, calendar = await self._input_data(model_run.horizon_max)
        bundle, manifest = load_bundle(model_run.artifact_path)
        try:
            raw = await asyncio.wait_for(
                run_in_threadpool(bundle.predict, history, calendar),
                timeout=self.settings.inference_timeout_seconds,
            )
        except TimeoutError as exc:
            raise AppError("INFERENCE_FAILED", 503, "Model inference timed out.") from exc
        except Exception as exc:
            raise AppError("INFERENCE_FAILED", 503, "Model inference failed.") from exc
        result = validate_forecast(raw, model_run.horizon_max)
        result = result[result["horizon"].isin(requested)]
        calendar_by_period = {row.period: row for row in (await self.session.execute(select(Calendar))).scalars()}
        items = []
        for row in result.itertuples(index=False):
            period = pd.Timestamp(row.period).date()
            cal = calendar_by_period.get(period)
            if cal is None:
                raise AppError("CALENDAR_INCOMPLETE", 503, f"Calendar missing for {period}.")
            risk = calculate_risk(row.upper95, cal.__dict__, self.settings)
            items.append(ForecastItem(
                period=period, horizon=row.horizon, point=row.point,
                intervals={"80": Interval(lower=row.lower80, upper=row.upper80), "95": Interval(lower=row.lower95, upper=row.upper95)},
                risk=risk,
            ))
        response = ForecastResponse(data=items, meta={
            "model_run_id": model_run.run_id, "algorithm": model_run.algorithm,
            "data_through": model_run.data_end.isoformat(), "cached": False,
            "unit": manifest.get("unit", "ribu_orang"), "available_horizons": list(range(1, model_run.horizon_max + 1)),
        })
        await self.redis.set(cache_key, response.model_dump_json(), ex=self.settings.forecast_cache_ttl_seconds)
        return response

    async def _active_model(self) -> ModelRun:
        model = (await self.session.execute(select(ModelRun).where(ModelRun.is_active.is_(True)))).scalar_one_or_none()
        if model is None:
            raise AppError("MODEL_NOT_AVAILABLE", 503, "No active model is available.")
        return model

    async def _input_data(self, horizon_max: int) -> tuple[pd.Series, pd.DataFrame]:
        actuals = (await self.session.execute(select(Actual).order_by(Actual.period))).scalars().all()
        if not actuals:
            raise AppError("DATA_NOT_AVAILABLE", 503, "No historical data is available.")
        history = pd.Series({pd.Timestamp(row.period): float(row.value_ribu) for row in actuals}).asfreq("MS")
        final_period = history.index.max() + pd.DateOffset(months=horizon_max)
        rows = (await self.session.execute(select(Calendar).where(Calendar.period <= final_period.date()).order_by(Calendar.period))).scalars().all()
        calendar = pd.DataFrame([{
            "period": pd.Timestamp(row.period), "total_hari": row.total_hari,
            "jumlah_hari_kerja": row.jumlah_hari_kerja,
            "jumlah_libur_nasional_weekday": row.jumlah_libur_nasional_weekday,
            "is_lebaran": row.is_lebaran, "is_covid": row.is_covid,
        } for row in rows]).set_index("period")
        if final_period not in calendar.index:
            raise AppError("CALENDAR_INCOMPLETE", 503, "Calendar does not cover the requested horizon.")
        return history, calendar
