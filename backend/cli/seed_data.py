"""Seed database from committed processed CSV files and outputs."""
import asyncio
from datetime import datetime, timezone
from pathlib import Path
import uuid

import pandas as pd
from sqlalchemy import delete, select

from backend.app.core.config import REPO_ROOT
from backend.app.db.base import Base
from backend.app.db.models import Actual, Calendar, Metric, ModelRun
from backend.app.db.session import SessionLocal, engine

ROOT = REPO_ROOT


async def seed_all(session=None) -> None:
    should_close_engine = False
    if session is None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        sess = SessionLocal()
        should_close_engine = True
    else:
        sess = session

    try:
        # 1. Seed Actuals
        actuals_file = ROOT / "data/processed/data_final.csv"
        if actuals_file.exists():
            actuals_df = pd.read_csv(actuals_file, parse_dates=["tanggal"])
            existing_actuals = set((await sess.execute(select(Actual.period))).scalars().all())
            new_actuals = [
                Actual(
                    period=row.tanggal.date(),
                    value_ribu=float(row.penumpang_ribu),
                    is_imputed=bool(getattr(row, "is_imputed", False)),
                    source="BPS",
                )
                for row in actuals_df.itertuples(index=False)
                if row.tanggal.date() not in existing_actuals
            ]
            if new_actuals:
                sess.add_all(new_actuals)

        # 2. Seed Calendar
        calendar_files = [ROOT / "data/processed/data_final.csv", ROOT / "data/processed/kalender_future.csv"]
        dfs = [pd.read_csv(f, parse_dates=["tanggal"]) for f in calendar_files if f.exists()]
        if dfs:
            calendar_df = pd.concat(dfs, ignore_index=True).drop_duplicates(subset=["tanggal"])
            existing_cals = set((await sess.execute(select(Calendar.period))).scalars().all())
            new_cals = [
                Calendar(
                    period=row.tanggal.date(),
                    total_hari=int(row.total_hari),
                    jumlah_hari_kerja=int(row.jumlah_hari_kerja),
                    jumlah_libur_nasional_weekday=int(row.jumlah_libur_nasional_weekday),
                    is_lebaran=bool(row.is_lebaran),
                    is_covid=bool(row.is_covid),
                    is_actual=not pd.isna(getattr(row, "penumpang_ribu", None)),
                )
                for row in calendar_df.itertuples(index=False)
                if row.tanggal.date() not in existing_cals
            ]
            if new_cals:
                sess.add_all(new_cals)

        # 3. Seed ModelRun (LightGBM CQR & SARIMAX)
        existing_runs = set((await sess.execute(select(ModelRun.run_id))).scalars().all())

        lgbm_run_id = "lgbm_cqr_v1"
        lgbm_run = None
        if lgbm_run_id not in existing_runs:
            lgbm_run = ModelRun(
                id=uuid.uuid4(),
                run_id=lgbm_run_id,
                algorithm="LightGBM + CQR",
                model_version="1.0.0",
                schema_version="1.0",
                data_start=pd.Timestamp("2016-01-01").date(),
                data_end=pd.Timestamp("2026-08-01").date(),
                horizon_max=6,
                artifact_path="outputs/prediksi_future_6bln.csv",
                checksum="precomputed_v1",
                library_versions={"lightgbm": "4.6.0", "pandas": "2.3.3"},
                model_card={
                    "description": "Multi-horizon LightGBM with Conformalized Quantile Regression (CQR)",
                    "best_subset": "bersih",
                    "mase_clean": 0.600,
                },
                trained_at=datetime.now(timezone.utc),
                is_active=True,
            )
            sess.add(lgbm_run)
            await sess.flush()
        else:
            lgbm_run = (await sess.execute(select(ModelRun).where(ModelRun.run_id == lgbm_run_id))).scalar_one()

        sarimax_run_id = "sarimax_v1"
        if sarimax_run_id not in existing_runs:
            sarimax_run = ModelRun(
                id=uuid.uuid4(),
                run_id=sarimax_run_id,
                algorithm="SARIMAX (Exogenous Calendar)",
                model_version="1.0.0",
                schema_version="1.0",
                data_start=pd.Timestamp("2016-01-01").date(),
                data_end=pd.Timestamp("2026-08-01").date(),
                horizon_max=6,
                artifact_path="outputs/backtest_sarimax_dan_baseline.csv",
                checksum="precomputed_v1",
                library_versions={"statsmodels": "0.14.0"},
                model_card={
                    "description": "SARIMAX(1,1,1)x(1,1,1,12) with exogenous calendar features",
                    "best_subset": "bersih",
                    "mase_clean": 0.524,
                },
                trained_at=datetime.now(timezone.utc),
                is_active=False,
            )
            sess.add(sarimax_run)
            await sess.flush()

        # 4. Seed Metrics
        metrics_file = ROOT / "outputs/metrik_komparasi_final.csv"
        metrics_per_h_file = ROOT / "outputs/metrik_per_horizon_final.csv"

        existing_metrics_count = (await sess.execute(select(Metric))).scalars().first()
        if existing_metrics_count is None and lgbm_run is not None:
            new_metrics = []
            if metrics_file.exists():
                m_df = pd.read_csv(metrics_file)
                lgbm_m = m_df[m_df["model"].str.lower().str.contains("lightgbm")]
                for row in lgbm_m.itertuples(index=False):
                    new_metrics.append(
                        Metric(
                            id=uuid.uuid4(),
                            model_run_id=lgbm_run.id,
                            subset=str(row.subset),
                            horizon=None,
                            n=int(row.n),
                            mae=float(row.MAE),
                            rmse=float(row.RMSE),
                            mase=float(row.MASE),
                            picp80=0.84,
                            picp95=1.00,
                        )
                    )
            if metrics_per_h_file.exists():
                mph_df = pd.read_csv(metrics_per_h_file)
                lgbm_mph = mph_df[mph_df["model"].str.lower().str.contains("lightgbm")]
                for row in lgbm_mph.itertuples(index=False):
                    new_metrics.append(
                        Metric(
                            id=uuid.uuid4(),
                            model_run_id=lgbm_run.id,
                            subset=str(row.subset),
                            horizon=int(row.horizon),
                            n=int(row.n),
                            mae=float(row.MAE),
                            rmse=float(row.RMSE),
                            mase=float(row.MASE),
                            picp80=0.84,
                            picp95=1.00,
                        )
                    )
            if new_metrics:
                sess.add_all(new_metrics)

        await sess.commit()
    finally:
        if should_close_engine:
            await sess.close()


def main() -> None:
    async def _runner():
        await seed_all()
        await engine.dispose()

    asyncio.run(_runner())


if __name__ == "__main__":
    main()
