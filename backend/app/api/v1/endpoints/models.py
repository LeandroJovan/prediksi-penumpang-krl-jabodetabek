from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import db_session
from backend.app.db.models import ModelRun

router = APIRouter(prefix="/models", tags=["models"])


@router.get("")
async def list_models(session: AsyncSession = Depends(db_session)) -> dict:
    rows = (await session.execute(select(ModelRun).order_by(ModelRun.trained_at.desc()))).scalars().all()
    return {"data": [{"run_id": row.run_id, "algorithm": row.algorithm, "model_version": row.model_version,
        "data_through": row.data_end, "horizon_max": row.horizon_max, "is_active": row.is_active} for row in rows]}


@router.get("/{run_id}")
async def model_detail(run_id: str, session: AsyncSession = Depends(db_session)) -> dict:
    row = (await session.execute(select(ModelRun).where(ModelRun.run_id == run_id))).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Model run not found")
    return {"data": {"run_id": row.run_id, "algorithm": row.algorithm, "model_card": row.model_card,
                      "library_versions": row.library_versions, "is_active": row.is_active}}
