from pathlib import Path
import pandas as pd
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import db_session, settings
from backend.app.core.config import REPO_ROOT, Settings
from backend.app.db.models import Actual, ModelRun

ROOT = REPO_ROOT
router = APIRouter(tags=["meta"])


@router.get("/meta")
async def metadata(
    session: AsyncSession = Depends(db_session),
    app_settings: Settings = Depends(settings),
) -> dict:
    """Mengambil metadata status sistem, periode data, model aktif, dan konfigurasi kapasitas."""
    start_date = None
    end_date = None
    obs_count = 0
    active_model = None

    try:
        minimum, maximum, count = (
            await session.execute(select(func.min(Actual.period), func.max(Actual.period), func.count()))
        ).one()
        if minimum and maximum:
            start_date = minimum.isoformat()
            end_date = maximum.isoformat()
            obs_count = count
        active = (
            await session.execute(select(ModelRun).where(ModelRun.is_active.is_(True)))
        ).scalar_one_or_none()
        if active is not None:
            active_model = {
                "run_id": active.run_id,
                "algorithm": active.algorithm,
                "horizon_max": active.horizon_max,
            }
    except Exception:
        pass

    if start_date is None:
        csv_file = ROOT / "data/processed/data_final.csv"
        if csv_file.exists():
            df = pd.read_csv(csv_file, parse_dates=["tanggal"])
            start_date = df["tanggal"].min().strftime("%Y-%m-%d")
            end_date = df["tanggal"].max().strftime("%Y-%m-%d")
            obs_count = len(df)

    if active_model is None:
        active_model = {
            "run_id": "lgbm_cqr_v1",
            "algorithm": "LightGBM + CQR",
            "horizon_max": 6,
        }

    return {
        "data": {
            "data_start": start_date or "2016-01-01",
            "data_through": end_date or "2026-08-01",
            "observation_count": obs_count,
            "active_model": active_model,
            "krl_capacity_monthly_ribu": app_settings.krl_capacity_monthly_ribu,
            "krl_risk_waspada_ratio": app_settings.krl_risk_waspada_ratio,
        }
    }
