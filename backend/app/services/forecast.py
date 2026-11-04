import asyncio
from datetime import date
from pathlib import Path

import pandas as pd
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import REPO_ROOT, Settings
from backend.app.core.errors import AppError
from backend.app.db.models import Actual, Calendar, ModelRun
from backend.app.ml.loader import load_bundle
from backend.app.ml.validation import validate_forecast
from backend.app.schemas.forecast import ForecastItem, ForecastResponse, Interval
from backend.app.services.risk import calculate_risk

ROOT = REPO_ROOT


class ForecastService:
    def __init__(self, session: AsyncSession, settings: Settings, redis) -> None:
        self.session, self.settings, self.redis = session, settings, redis

    async def latest(
        self,
        horizons: list[int] | None = None,
        capacity_monthly: float | None = None,
        waspada_ratio: float | None = None,
        basis_col: str = "95",
    ) -> ForecastResponse:
        model_run = await self._active_model_or_default()
        horizon_max = model_run.horizon_max if model_run else 6
        requested = horizons or list(range(1, horizon_max + 1))
        if any(h < 1 or h > horizon_max for h in requested):
            raise AppError("HORIZON_NOT_AVAILABLE", 422, "Requested horizon is not available.")

        run_id = model_run.run_id if model_run else "precomputed_lgbm_cqr"
        cap_monthly = capacity_monthly if capacity_monthly is not None else self.settings.krl_capacity_monthly_ribu
        ratio = waspada_ratio if waspada_ratio is not None else self.settings.krl_risk_waspada_ratio
        capacity_key = f"{cap_monthly}:{self.settings.krl_capacity_weekday_ribu}:{self.settings.krl_capacity_weekend_ribu}:{ratio}:{basis_col}"
        cache_key = f"forecast:v1:{run_id}:{','.join(map(str, sorted(requested)))}:{capacity_key}"

        if self.redis is not None:
            cached = await self.redis.get(cache_key)
            if cached:
                return ForecastResponse.model_validate_json(cached)

        # 1. Coba inference via bundle jika model artifact tersedia
        items = None
        manifest_unit = "ribu_orang"
        if model_run and Path(model_run.artifact_path).is_dir():
            try:
                history, calendar = await self._input_data(model_run.horizon_max)
                bundle, manifest = load_bundle(model_run.artifact_path)
                manifest_unit = manifest.get("unit", "ribu_orang")
                raw = await asyncio.wait_for(
                    run_in_threadpool(bundle.predict, history, calendar),
                    timeout=self.settings.inference_timeout_seconds,
                )
                result = validate_forecast(raw, model_run.horizon_max)
                result = result[result["horizon"].isin(requested)]
                items = await self._build_items_from_prediction(
                    result,
                    capacity_monthly=cap_monthly,
                    waspada_ratio=ratio,
                    basis_col=basis_col,
                )
            except Exception:
                items = None

        # 2. Fallback ke output pipeline ML yang sudah divalidasi (outputs/prediksi_future_6bln.csv)
        if items is None:
            items = await self._build_items_from_csv(
                requested,
                capacity_monthly=cap_monthly,
                waspada_ratio=ratio,
                basis_col=basis_col,
            )

        response = ForecastResponse(
            data=items,
            meta={
                "model_run_id": run_id,
                "algorithm": model_run.algorithm if model_run else "LightGBM + Conformal CQR",
                "data_through": model_run.data_end.isoformat() if model_run else "2026-08-01",
                "cached": False,
                "unit": manifest_unit,
                "available_horizons": list(range(1, horizon_max + 1)),
                "ambang_kapasitas_aktif": cap_monthly,
                "batas_waspada_rasio": ratio,
            },
        )

        if self.redis is not None:
            await self.redis.set(cache_key, response.model_dump_json(), ex=self.settings.forecast_cache_ttl_seconds)

        return response

    async def _active_model_or_default(self) -> ModelRun | None:
        try:
            return (
                await self.session.execute(select(ModelRun).where(ModelRun.is_active.is_(True)))
            ).scalar_one_or_none()
        except Exception:
            return None

    async def _build_items_from_prediction(
        self,
        df_result: pd.DataFrame,
        capacity_monthly: float,
        waspada_ratio: float,
        basis_col: str,
    ) -> list[ForecastItem]:
        calendar_by_period = {
            row.period: row for row in (await self.session.execute(select(Calendar))).scalars()
        }
        items = []
        for row in df_result.itertuples(index=False):
            period = pd.Timestamp(row.period).date()
            cal = calendar_by_period.get(period)
            cal_dict = cal.__dict__ if cal else {"total_hari": 30, "jumlah_hari_kerja": 21}
            upper_val = getattr(row, f"upper{basis_col}", row.upper95)
            risk = calculate_risk(
                upper_val,
                cal_dict,
                self.settings,
                capacity_monthly_override=capacity_monthly,
                waspada_ratio_override=waspada_ratio,
            )
            risk.basis = f"upper{basis_col}"
            items.append(
                ForecastItem(
                    period=period,
                    horizon=row.horizon,
                    point=round(float(row.point), 1),
                    intervals={
                        "80": Interval(lower=round(float(row.lower80), 1), upper=round(float(row.upper80), 1)),
                        "95": Interval(lower=round(float(row.lower95), 1), upper=round(float(row.upper95), 1)),
                    },
                    risk=risk,
                )
            )
        return items

    async def _build_items_from_csv(
        self,
        requested_horizons: list[int],
        capacity_monthly: float,
        waspada_ratio: float,
        basis_col: str,
    ) -> list[ForecastItem]:
        csv_path = ROOT / "outputs/prediksi_future_6bln.csv"
        if not csv_path.exists():
            raise AppError("DATA_NOT_AVAILABLE", 503, "Forecast output CSV not found.")

        df = pd.read_csv(csv_path)
        df = df[df["horizon"].isin(requested_horizons)]

        calendar_by_period = {}
        try:
            rows = (await self.session.execute(select(Calendar))).scalars().all()
            calendar_by_period = {row.period: row.__dict__ for row in rows}
        except Exception:
            pass

        items = []
        for row in df.itertuples(index=False):
            h = int(row.horizon)
            # 6 bulan ke depan mulai 2026-09-01
            period = (pd.Timestamp("2026-08-01") + pd.DateOffset(months=h)).date()
            cal_dict = calendar_by_period.get(period, {"total_hari": 30, "jumlah_hari_kerja": 21})

            val_80_lo = float(row.batas_bawah_80)
            val_80_hi = float(row.batas_atas_80)
            val_95_lo = float(row.batas_bawah_95)
            val_95_hi = float(row.batas_atas_95)

            upper_val = val_80_hi if basis_col == "80" else val_95_hi

            risk = calculate_risk(
                upper_val,
                cal_dict,
                self.settings,
                capacity_monthly_override=capacity_monthly,
                waspada_ratio_override=waspada_ratio,
            )
            risk.basis = f"upper{basis_col}"

            items.append(
                ForecastItem(
                    period=period,
                    horizon=h,
                    point=round(float(row.y_pred_titik), 1),
                    intervals={
                        "80": Interval(lower=round(val_80_lo, 1), upper=round(val_80_hi, 1)),
                        "95": Interval(lower=round(val_95_lo, 1), upper=round(val_95_hi, 1)),
                    },
                    risk=risk,
                )
            )
        return items

    async def _input_data(self, horizon_max: int) -> tuple[pd.Series, pd.DataFrame]:
        actuals = (await self.session.execute(select(Actual).order_by(Actual.period))).scalars().all()
        if not actuals:
            raise AppError("DATA_NOT_AVAILABLE", 503, "No historical data is available.")
        history = pd.Series({pd.Timestamp(row.period): float(row.value_ribu) for row in actuals}).asfreq("MS")
        final_period = history.index.max() + pd.DateOffset(months=horizon_max)
        rows = (
            await self.session.execute(
                select(Calendar).where(Calendar.period <= final_period.date()).order_by(Calendar.period)
            )
        ).scalars().all()
        calendar = pd.DataFrame(
            [
                {
                    "period": pd.Timestamp(row.period),
                    "total_hari": row.total_hari,
                    "jumlah_hari_kerja": row.jumlah_hari_kerja,
                    "jumlah_libur_nasional_weekday": row.jumlah_libur_nasional_weekday,
                    "is_lebaran": row.is_lebaran,
                    "is_covid": row.is_covid,
                }
                for row in rows
            ]
        ).set_index("period")
        return history, calendar
