from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import db_session
from backend.app.db.models import ModelRun

router = APIRouter(prefix="/models", tags=["models"])

DEFAULT_MODELS = [
    {
        "run_id": "lgbm_cqr_v1",
        "algorithm": "LightGBM + CQR",
        "model_version": "1.0.0",
        "data_through": "2026-08-01",
        "horizon_max": 6,
        "is_active": True,
        "description": "Multi-Horizon LightGBM dengan Conformalized Quantile Regression (CQR)",
    },
    {
        "run_id": "sarimax_v1",
        "algorithm": "SARIMAX (Exogenous Calendar)",
        "model_version": "1.0.0",
        "data_through": "2026-08-01",
        "horizon_max": 6,
        "is_active": False,
        "description": "SARIMAX(1,1,1)x(1,1,1,12) dengan fitur kalender hari kerja & Lebaran",
    },
    {
        "run_id": "ets_v1",
        "algorithm": "ETS (Holt-Winters)",
        "model_version": "1.0.0",
        "data_through": "2026-08-01",
        "horizon_max": 6,
        "is_active": False,
        "description": "Exponential Smoothing Holt-Winters Musiman Additive",
    },
]


@router.get("")
async def list_models(session: AsyncSession = Depends(db_session)) -> dict:
    """Mengambil daftar model yang tersedia dalam sistem."""
    try:
        rows = (await session.execute(select(ModelRun).order_by(ModelRun.trained_at.desc()))).scalars().all()
        if rows:
            return {
                "data": [
                    {
                        "run_id": row.run_id,
                        "algorithm": row.algorithm,
                        "model_version": row.model_version,
                        "data_through": row.data_end.isoformat(),
                        "horizon_max": row.horizon_max,
                        "is_active": row.is_active,
                    }
                    for row in rows
                ]
            }
    except Exception:
        pass

    return {"data": DEFAULT_MODELS}


@router.get("/{run_id}")
async def model_detail(run_id: str, session: AsyncSession = Depends(db_session)) -> dict:
    """Mengambil detail konfigurasi dan kartu model berdasarkan run_id."""
    try:
        row = (await session.execute(select(ModelRun).where(ModelRun.run_id == run_id))).scalar_one_or_none()
        if row is not None:
            return {
                "data": {
                    "run_id": row.run_id,
                    "algorithm": row.algorithm,
                    "model_card": row.model_card,
                    "library_versions": row.library_versions,
                    "is_active": row.is_active,
                }
            }
    except Exception:
        pass

    for m in DEFAULT_MODELS:
        if m["run_id"] == run_id:
            return {"data": m}

    raise HTTPException(status_code=404, detail="Model run not found")
