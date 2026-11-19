import json
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
DATA_JSON = ROOT / "frontend" / "data" / "data.json"
PREDIKSI_CSV = ROOT / "outputs" / "prediksi_future_6bln.csv"
STATUS_CSV = ROOT / "outputs" / "tabel_status_risiko_kapasitas.csv"


@pytest.fixture(scope="module")
def dashboard():
    return json.loads(DATA_JSON.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def prediksi():
    return pd.read_csv(PREDIKSI_CSV).sort_values("horizon").reset_index(drop=True)


def _status_frontend(u95: float, ambang: float) -> str:
    if u95 is None or not ambang:
        return "menunggu data"
    p = (u95 / ambang) * 100
    return "kritis" if p >= 100 else "waspada" if p >= 90 else "aman"


def test_titik_data_json_sama_dengan_csv(dashboard, prediksi):
    forecast = dashboard["forecast"]
    assert len(forecast) == len(prediksi)
    for baris, csv in zip(forecast, prediksi.itertuples(index=False)):
        assert baris["bulan"] == pd.Timestamp(csv.tanggal_target).strftime("%Y-%m")
        assert abs(baris["titik"] - csv.y_pred) <= 1, baris["bulan"]


def test_lebar_interval_bervariasi_antar_horizon(dashboard, prediksi):
    fc = dashboard["forecast"]
    lebar_95 = [r["u95"] - r["l95"] for r in fc]
    lebar_80 = [r["u80"] - r["l80"] for r in fc]
    assert len(set(lebar_95)) > 1, f"lebar 95% konstan: {lebar_95}"
    assert len(set(lebar_80)) > 1, f"lebar 80% konstan: {lebar_80}"

    lebar_95_csv = (prediksi["upper_95"] - prediksi["lower_95"]).round().astype(int).tolist()
    for a, b in zip(lebar_95, lebar_95_csv):
        assert abs(a - b) <= 2, (lebar_95, lebar_95_csv)


def test_status_risiko_sama_dengan_tabel_kalibrasi(dashboard):
    ambang = dashboard["ambang_kapasitas"]["nilai"]
    status_csv = pd.read_csv(STATUS_CSV).sort_values("horizon").reset_index(drop=True)
    forecast = dashboard["forecast"]

    assert len(forecast) == len(status_csv)
    for baris, csv in zip(forecast, status_csv.itertuples(index=False)):
        assert baris["bulan"] == pd.Timestamp(csv.tanggal_target).strftime("%Y-%m")
        assert _status_frontend(baris["u95"], ambang) == csv.status_risiko.lower()
