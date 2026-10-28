from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import db_session
from backend.app.db.models import Actual

router = APIRouter(prefix="/passengers", tags=["passengers"])


@router.get("")
async def list_passengers(
    start: date | None = None, end: date | None = None, limit: int = Query(default=200, le=500),
    session: AsyncSession = Depends(db_session),
) -> dict:
    statement = select(Actual).order_by(Actual.period).limit(limit)
    if start:
        statement = statement.where(Actual.period >= start)
    if end:
        statement = statement.where(Actual.period <= end)
    rows = (await session.execute(statement)).scalars().all()
    return {"data": [{"period": row.period, "value_ribu": float(row.value_ribu), "is_imputed": row.is_imputed} for row in rows]}
