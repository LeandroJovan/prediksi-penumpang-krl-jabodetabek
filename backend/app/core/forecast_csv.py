"""Pembaca tunggal untuk outputs/prediksi_future_6bln.csv.

Pipeline ML pernah mengganti nama kolom (mis. ``y_pred_titik`` -> ``y_pred``).
Modul ini menormalkan semua varian nama ke skema kanonik yang dipakai backend,
dan gagal dengan pesan jelas jika kolom wajib tidak ada.
"""
from pathlib import Path

import pandas as pd

from backend.app.core.pipeline_data import target_periods

CANONICAL_COLUMNS = [
    "horizon",
    "y_pred_titik",
    "batas_bawah_80",
    "batas_atas_80",
    "batas_bawah_95",
    "batas_atas_95",
]

COLUMN_ALIASES = {
    "y_pred": "y_pred_titik",
    "lower_80": "batas_bawah_80",
    "upper_80": "batas_atas_80",
    "lower_95": "batas_bawah_95",
    "upper_95": "batas_atas_95",
}


class ForecastCsvError(ValueError):
    """CSV prakiraan tidak sesuai kontrak kolom."""


def normalize_forecast_frame(df: pd.DataFrame, with_period: bool = True) -> pd.DataFrame:
    df = df.rename(columns=COLUMN_ALIASES)
    missing = [c for c in CANONICAL_COLUMNS if c not in df.columns]
    if missing:
        raise ForecastCsvError(f"Kolom prakiraan tidak ditemukan: {', '.join(missing)}")
    if with_period:
        try:
            df = df.assign(period_target=target_periods(df))
        except ValueError as exc:
            raise ForecastCsvError(str(exc)) from exc
    return df


def read_forecast_csv(path: Path, with_period: bool = True) -> pd.DataFrame:
    """with_period=True menambah kolom ``period_target`` (date) untuk tiap horizon."""
    return normalize_forecast_frame(pd.read_csv(path), with_period=with_period)
