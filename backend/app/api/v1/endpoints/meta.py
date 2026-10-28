from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import db_session
from backend.app.db.models import Actual, ModelRun

router = APIRouter(tags=["meta"])


@router.get("/meta")
async def metadata(session: AsyncSession = Depends(db_session)) -> dict:
    minimum, maximum, count = (await session.execute(select(func.min(Actual.period), func.max(Actual.period), func.count()))).one()
    active = (await session.execute(select(ModelRun).where(ModelRun.is_active.is_(True)))).scalar_one_or_none()
    return {"data": {"data_start": minimum, "data_through": maximum, "observation_count": count,
        "active_model": None if active is None else {"run_id": active.run_id, "algorithm": active.algorithm, "horizon_max": active.horizon_max}}}
