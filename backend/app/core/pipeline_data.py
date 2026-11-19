"""Batas periode data dan periode target prakiraan, diturunkan dari output pipeline.

Menggantikan tanggal hardcoded (mis. 2026-08-01) agar backend tetap benar saat data bulan baru masuk.
"""
from datetime import date
from functools import lru_cache
from pathlib import Path

import pandas as pd
from fastapi.concurrency import run_in_threadpool

from backend.app.core.config import REPO_ROOT

DATA_FINAL = "data/processed/data_final.csv"


@lru_cache(maxsize=4)
def _bounds(path: str, mtime_ns: int) -> tuple[date | None, date | None]:
    # mtime_ns ikut menjadi kunci cache sehingga file yang diperbarui otomatis terbaca ulang.
    series = pd.read_csv(path, usecols=["tanggal"], parse_dates=["tanggal"])["tanggal"].dropna()
    if series.empty:
        return None, None
    return series.min().date(), series.max().date()


def data_bounds(root: Path = REPO_ROOT) -> tuple[date | None, date | None]:
    """(bulan pertama, bulan terakhir) data aktual; (None, None) jika file tidak ada."""
    path = root / DATA_FINAL
    if not path.exists():
        return None, None
    return _bounds(str(path), path.stat().st_mtime_ns)


async def read_csv_async(path: Path, **kwargs) -> pd.DataFrame:
    """pd.read_csv di threadpool agar tidak memblokir event loop."""
    return await run_in_threadpool(pd.read_csv, path, **kwargs)


def target_periods(frame: pd.DataFrame, last_actual: date | None = None) -> list[date]:
    """Periode (awal bulan) tiap baris prakiraan.

    Memakai kolom ``tanggal_target`` dari pipeline bila ada; jika tidak, dihitung dari bulan aktual
    terakhir + horizon. Melempar ValueError jika keduanya tidak tersedia.
    """
    if "tanggal_target" in frame.columns:
        return [pd.Timestamp(value).date() for value in frame["tanggal_target"]]
    last = last_actual or data_bounds()[1]
    if last is None:
        raise ValueError("Periode target tidak dapat ditentukan: tanggal_target dan data aktual tidak ada.")
    return [(pd.Timestamp(last) + pd.DateOffset(months=int(h))).date() for h in frame["horizon"]]
