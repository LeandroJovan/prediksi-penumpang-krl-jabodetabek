from datetime import date
from pathlib import Path
import pandas as pd
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import db_session
from backend.app.core.config import REPO_ROOT
from backend.app.db.models import Actual

ROOT = REPO_ROOT
router = APIRouter(prefix="/passengers", tags=["passengers"])


@router.get("")
async def list_passengers(
    start: date | None = None,
    end: date | None = None,
    limit: int = Query(default=200, le=500),
    session: AsyncSession = Depends(db_session),
) -> dict:
    """Mengambil data deret waktu penumpang historis bulanan BPS."""
    statement = select(Actual).order_by(Actual.period).limit(limit)
    if start:
        statement = statement.where(Actual.period >= start)
    if end:
        statement = statement.where(Actual.period <= end)

    rows = []
    try:
        rows = (await session.execute(statement)).scalars().all()
    except Exception:
        rows = []

    if rows:
        return {
            "data": [
                {
                    "period": row.period.isoformat(),
                    "value_ribu": float(row.value_ribu),
                    "is_imputed": row.is_imputed,
                }
                for row in rows
            ]
        }

    # Fallback ke CSV jika DB belum terisi
    csv_file = ROOT / "data/processed/data_final.csv"
    if csv_file.exists():
        df = pd.read_csv(csv_file, parse_dates=["tanggal"])
        if start:
            df = df[df["tanggal"].dt.date >= start]
        if end:
            df = df[df["tanggal"].dt.date <= end]
        df = df.head(limit)
        return {
            "data": [
                {
                    "period": row.tanggal.strftime("%Y-%m-%d"),
                    "value_ribu": float(row.penumpang_ribu),
                    "is_imputed": bool(getattr(row, "is_imputed", False)),
                }
                for row in df.itertuples(index=False)
            ]
        }

    return {"data": []}
