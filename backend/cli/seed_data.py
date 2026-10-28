"""Seed PostgreSQL from committed processed CSV files."""
import asyncio
from pathlib import Path

import pandas as pd
from sqlalchemy.dialects.postgresql import insert

from backend.app.db.base import Base
from backend.app.db.models import Actual, Calendar
from backend.app.db.session import SessionLocal, engine

ROOT = Path(__file__).resolve().parents[2]


async def main() -> None:
    actuals = pd.read_csv(ROOT / "data/processed/data_final.csv", parse_dates=["tanggal"])
    future = pd.read_csv(ROOT / "data/processed/kalender_future.csv", parse_dates=["tanggal"])
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with SessionLocal() as session:
        for row in actuals.itertuples(index=False):
            await session.execute(insert(Actual).values(period=row.tanggal.date(), value_ribu=row.penumpang_ribu,
                is_imputed=bool(getattr(row, "is_imputed", False)), source="BPS").on_conflict_do_update(
                index_elements=[Actual.period], set_={"value_ribu": row.penumpang_ribu, "source": "BPS"}))
        calendar = pd.concat([actuals, future], ignore_index=True)
        for row in calendar.itertuples(index=False):
            await session.execute(insert(Calendar).values(period=row.tanggal.date(), total_hari=row.total_hari,
                jumlah_hari_kerja=row.jumlah_hari_kerja,
                jumlah_libur_nasional_weekday=row.jumlah_libur_nasional_weekday,
                is_lebaran=bool(row.is_lebaran), is_covid=bool(row.is_covid),
                is_actual=not pd.isna(getattr(row, "penumpang_ribu", None))).on_conflict_do_update(
                index_elements=[Calendar.period], set_={"total_hari": row.total_hari, "jumlah_hari_kerja": row.jumlah_hari_kerja,
                "jumlah_libur_nasional_weekday": row.jumlah_libur_nasional_weekday, "is_lebaran": bool(row.is_lebaran),
                "is_covid": bool(row.is_covid)}))
        await session.commit()
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
