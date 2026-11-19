"""Statistik riwayat yang dihitung langsung dari data, sebagai fakta untuk chatbot.

Angka seperti dampak Lebaran atau korelasi hari kerja TIDAK boleh ditulis tangan: harus berasal dari data
yang sama dengan model, sehingga ikut berubah ketika data baru masuk.
"""
import logging
from functools import lru_cache
from pathlib import Path

import pandas as pd

from backend.app.core.config import REPO_ROOT
from backend.app.core.pipeline_data import DATA_FINAL, load_picp

logger = logging.getLogger("krl_backend.chat_stats")
INTERVAL_CSV = "outputs/metrik_interval_conformal.csv"


def _pct(new: float, base: float) -> float | None:
    return float((new - base) / base * 100.0) if base else None


@lru_cache(maxsize=2)
def _compute(path: str, mtime_ns: int) -> dict:
    df = pd.read_csv(path, parse_dates=["tanggal"]).sort_values("tanggal").reset_index(drop=True)
    values = df["penumpang_ribu"].astype(float)
    covid = df["is_covid"].astype(bool)

    # Efek Lebaran: selisih bulan Lebaran terhadap rata-rata bulan sebelum & sesudahnya (di luar pandemi,
    # karena saat pandemi penyebab penurunan tercampur).
    events = []
    for i in df.index[df["is_lebaran"].astype(bool)]:
        if 0 < i < len(df) - 1 and not covid[i]:
            pct = _pct(values[i], (values[i - 1] + values[i + 1]) / 2.0)
            if pct is not None:
                events.append({"period": df.loc[i, "tanggal"].strftime("%Y-%m"), "pct": pct})
    recent, earlier = events[-3:], events[:-3]

    non_covid = df[~covid]
    corr = non_covid["penumpang_ribu"].corr(non_covid["jumlah_hari_kerja"]) if len(non_covid) > 2 else None

    covid_stats = None
    if covid.any():
        first = df.index[covid][0]
        pre = values[max(0, first - 12):first]
        if len(pre):
            base = float(pre.mean())
            covid_stats = {
                "months": int(covid.sum()),
                "first": df.loc[first, "tanggal"].strftime("%Y-%m"),
                "last": df.loc[df.index[covid][-1], "tanggal"].strftime("%Y-%m"),
                "mean_pct": _pct(float(values[covid].mean()), base),
                "lowest_pct": _pct(float(values[covid].min()), base),
            }

    return {
        "n_obs": int(len(df)),
        "data_start": df["tanggal"].min().strftime("%Y-%m"),
        "last_period": df["tanggal"].max().strftime("%Y-%m"),
        "last_value": float(values.iloc[-1]),
        "lebaran_events": events,
        "lebaran_mean_pct": float(sum(e["pct"] for e in events) / len(events)) if events else None,
        "lebaran_recent_pct": float(sum(e["pct"] for e in recent) / len(recent)) if recent else None,
        "lebaran_earlier_pct": float(sum(e["pct"] for e in earlier) / len(earlier)) if earlier else None,
        "lebaran_recent_periods": [e["period"] for e in recent],
        "workday_corr": None if corr is None or pd.isna(corr) else float(corr),
        "covid": covid_stats,
    }


def history_stats(root: Path = REPO_ROOT) -> dict | None:
    """Statistik riwayat + cakupan interval hasil backtest; None jika data riwayat tidak tersedia."""
    path = root / DATA_FINAL
    if not path.exists():
        return None
    stats = dict(_compute(str(path), path.stat().st_mtime_ns))
    try:
        _, (p80, p95) = load_picp(root / INTERVAL_CSV)
    except Exception:
        logger.exception("Gagal membaca cakupan interval (PICP)")
        p80 = p95 = None
    stats["picp80_pct"] = None if p80 is None else p80 * 100.0
    stats["picp95_pct"] = None if p95 is None else p95 * 100.0
    return stats
