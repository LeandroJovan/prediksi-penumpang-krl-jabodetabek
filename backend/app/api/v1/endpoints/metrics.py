from pathlib import Path
import pandas as pd
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import db_session
from backend.app.core.config import REPO_ROOT
from backend.app.db.models import Metric, ModelRun

ROOT = REPO_ROOT
router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("")
async def list_metrics(
    model_run_id: str | None = None,
    subset: str | None = None,
    horizon: int | None = Query(default=None, ge=1),
    session: AsyncSession = Depends(db_session),
) -> dict:
    """Mengambil metrik evaluasi model (MASE, MAE, RMSE, MAPE, PICP) dari DB atau artefak CSV."""
    statement = select(Metric, ModelRun.run_id).join(ModelRun, Metric.model_run_id == ModelRun.id)
    if model_run_id:
        statement = statement.where(ModelRun.run_id == model_run_id)
    if subset:
        statement = statement.where(Metric.subset == subset)
    if horizon:
        statement = statement.where(Metric.horizon == horizon)

    rows = []
    try:
        rows = (await session.execute(statement)).all()
    except Exception:
        rows = []

    if rows:
        data = [
            {
                "model_run_id": run_id,
                "subset": metric.subset,
                "horizon": metric.horizon,
                "n": metric.n,
                "mae": float(metric.mae) if metric.mae is not None else None,
                "rmse": float(metric.rmse) if metric.rmse is not None else None,
                "mase": float(metric.mase) if metric.mase is not None else None,
                "picp80": float(metric.picp80) if metric.picp80 is not None else None,
                "picp95": float(metric.picp95) if metric.picp95 is not None else None,
            }
            for metric, run_id in rows
        ]
        return {"data": data}

    # Fallback langsung ke CSV output jika DB belum di-populate
    if horizon is not None:
        csv_file = ROOT / "outputs/metrik_per_horizon_final.csv"
        if csv_file.exists():
            df = pd.read_csv(csv_file)
            if subset:
                df = df[df["subset"] == subset]
            df = df[df["horizon"] == horizon]
            return {
                "data": [
                    {
                        "model": row.model,
                        "subset": row.subset,
                        "horizon": int(row.horizon),
                        "n": int(row.n),
                        "mae": round(float(row.MAE), 1),
                        "rmse": round(float(row.RMSE), 1),
                        "mape_%": round(float(getattr(row, "MAPE_%", 0)), 2),
                        "mase": round(float(row.MASE), 3),
                    }
                    for row in df.itertuples(index=False)
                ]
            }

    csv_file = ROOT / "outputs/metrik_komparasi_final.csv"
    if csv_file.exists():
        df = pd.read_csv(csv_file)
        if subset:
            df = df[df["subset"] == subset]
        return {
            "data": [
                {
                    "model": row.model,
                    "subset": row.subset,
                    "horizon": None,
                    "n": int(row.n),
                    "mae": round(float(row.MAE), 1),
                    "rmse": round(float(row.RMSE), 1),
                    "mape_%": round(float(getattr(row, "MAPE_%", 0)), 2),
                    "mase": round(float(row.MASE), 3),
                }
                for row in df.itertuples(index=False)
            ]
        }

    return {"data": []}
