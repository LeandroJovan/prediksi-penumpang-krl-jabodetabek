from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import db_session
from backend.app.db.models import Metric, ModelRun

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("")
async def list_metrics(
    model_run_id: str | None = None, subset: str | None = None, horizon: int | None = Query(default=None, ge=1),
    session: AsyncSession = Depends(db_session),
) -> dict:
    statement = select(Metric, ModelRun.run_id).join(ModelRun, Metric.model_run_id == ModelRun.id)
    if model_run_id:
        statement = statement.where(ModelRun.run_id == model_run_id)
    if subset:
        statement = statement.where(Metric.subset == subset)
    if horizon:
        statement = statement.where(Metric.horizon == horizon)
    rows = (await session.execute(statement)).all()
    return {"data": [{"model_run_id": run_id, "subset": metric.subset, "horizon": metric.horizon, "n": metric.n,
        "mae": float(metric.mae) if metric.mae is not None else None, "rmse": float(metric.rmse) if metric.rmse is not None else None,
        "mase": float(metric.mase) if metric.mase is not None else None, "picp80": float(metric.picp80) if metric.picp80 is not None else None,
        "picp95": float(metric.picp95) if metric.picp95 is not None else None} for metric, run_id in rows]}
