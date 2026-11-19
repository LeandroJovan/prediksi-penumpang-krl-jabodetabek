"""
export_app_data.py
------------------
Script untuk menyambungkan hasil data preparation, backtesting,
dan model machine learning dari tim ke dashboard frontend (frontend/data/data.json).

Dijalankan secara otomatis atau manual saat ada pembaruan data/model:
    python src/export_app_data.py
"""

import json
import os
import sys
from datetime import datetime
import numpy as np
import pandas as pd

# Tambahkan direktori src ke path
DIR_SRC = os.path.dirname(os.path.abspath(__file__))
DIR_ROOT = os.path.dirname(DIR_SRC)
sys.path.append(DIR_SRC)

import config as cfg
import metrics as mt

PATH_DATA_FINAL = os.path.join(DIR_ROOT, "data", "processed", "data_final.csv")
PATH_METRIK_BASELINE = os.path.join(DIR_ROOT, "outputs", "metrik_baseline.csv")
PATH_BACKTEST_BASELINE = os.path.join(DIR_ROOT, "outputs", "backtest_baseline.csv")
PATH_PREDIKSI = os.path.join(DIR_ROOT, "outputs", "prediksi_future_6bln.csv")
PATH_Q_HAT = os.path.join(DIR_ROOT, "outputs", "q_hat_conformal.csv")
PATH_OUTPUT_JSON = os.path.join(DIR_ROOT, "frontend", "data", "data.json")

# Kolom interval pada outputs/prediksi_future_6bln.csv
KOLOM_TITIK_CSV = "y_pred"
KOLOM_INTERVAL_CSV = {
    0.80: ("lower_80", "upper_80"),
    0.95: ("lower_95", "upper_95"),
}
# Toleransi konsistensi antara interval CSV dan (titik + q_hat)
TOLERANSI_Q = 1.0


def generate_dashboard_data():
    if not os.path.exists(PATH_DATA_FINAL):
        raise FileNotFoundError(f"File {PATH_DATA_FINAL} tidak ditemukan!")

    # 1. Muat Data Historis
    df = pd.read_csv(PATH_DATA_FINAL)
    df["tanggal"] = pd.to_datetime(df["tanggal"])
    df = df.sort_values("tanggal").reset_index(drop=True)

    # Historis JSON list
    historis = []
    for _, row in df.iterrows():
        historis.append({
            "bulan": str(row["year_month"]),
            "nilai": float(row["penumpang_ribu"]),
            "hari_kerja": int(row["jumlah_hari_kerja"]) if pd.notna(row["jumlah_hari_kerja"]) else None
        })

    # Bulan Lebaran (is_lebaran == 1)
    lebaran_months = df[df["is_lebaran"] == 1]["year_month"].astype(str).tolist()

    periode_awal = historis[0]["bulan"]
    periode_akhir = historis[-1]["bulan"]
    periode_data = f"{periode_awal} s.d. {periode_akhir}"

    # 2. Ambang Kapasitas
    # Default dari config jika ada, atau nilai estimasi sistem (mis. 34.000 ribu / ~5% di atas rekor historis)
    max_hist = df["penumpang_ribu"].max()
    ambang_nilai = cfg.AMBANG_KAPASITAS if (hasattr(cfg, "AMBANG_KAPASITAS") and cfg.AMBANG_KAPASITAS is not None) else 34000

    # 3. Peramalan & Interval (sumber: keluaran pipeline terkalibrasi)
    # Titik dan interval dibaca apa adanya dari outputs/prediksi_future_6bln.csv
    # (LightGBM per hari kerja + interval conformal bergulir). q per-horizon
    # dibaca dari outputs/q_hat_conformal.csv untuk dicatat dan divalidasi.
    if not os.path.exists(PATH_PREDIKSI):
        raise FileNotFoundError(
            f"File {PATH_PREDIKSI} tidak ditemukan! Jalankan 'python src/peramalan.py' lebih dulu."
        )
    if not os.path.exists(PATH_Q_HAT):
        raise FileNotFoundError(
            f"File {PATH_Q_HAT} tidak ditemukan! Kalibrasi conformal belum dijalankan."
        )

    horizon_maks = getattr(cfg, "HORIZON_MAKS", 6)

    pred_df = pd.read_csv(PATH_PREDIKSI)
    pred_df["tanggal_target"] = pd.to_datetime(pred_df["tanggal_target"])
    pred_df = pred_df.sort_values("horizon").reset_index(drop=True)
    pred_df = pred_df.iloc[:horizon_maks]

    if list(pred_df["horizon"]) != list(range(1, horizon_maks + 1)):
        raise ValueError(
            f"{PATH_PREDIKSI} harus berisi horizon 1..{horizon_maks} tanpa celah/duplikat."
        )

    q_df = pd.read_csv(PATH_Q_HAT)
    q_per_horizon = {}
    for level, (_, _) in KOLOM_INTERVAL_CSV.items():
        sub_level = q_df[np.isclose(q_df["level"], level, atol=1e-9)]
        q_map = {}
        for h in range(1, horizon_maks + 1):
            baris_q = sub_level[sub_level["horizon"] == h]
            if baris_q.empty:
                raise ValueError(
                    f"q_hat level {level} horizon {h} tidak ditemukan di {PATH_Q_HAT}."
                )
            q_map[h] = {
                "q_lo": float(baris_q["q_lo"].iloc[0]),
                "q_hi": float(baris_q["q_hi"].iloc[0]),
            }
        q_per_horizon[level] = q_map

    # Bentuk array forecast untuk 6 bulan ke depan; validasi CSV == titik + q_hat
    forecast = []
    for baris in pred_df.itertuples(index=False):
        h = int(baris.horizon)
        pt = float(getattr(baris, KOLOM_TITIK_CSV))
        interval = {}
        for level, (kol_lo, kol_hi) in KOLOM_INTERVAL_CSV.items():
            lo = float(getattr(baris, kol_lo))
            hi = float(getattr(baris, kol_hi))
            q = q_per_horizon[level][h]
            if (abs((pt + q["q_lo"]) - lo) > TOLERANSI_Q
                    or abs((pt + q["q_hi"]) - hi) > TOLERANSI_Q):
                raise ValueError(
                    f"Interval {int(level * 100)}% horizon {h} pada {PATH_PREDIKSI} "
                    f"tidak konsisten dengan titik + q_hat ({PATH_Q_HAT}). "
                    "Regenerasi prediksi_future_6bln.csv dari q_hat terbaru."
                )
            interval[level] = (lo, hi)

        forecast.append({
            "bulan": baris.tanggal_target.strftime("%Y-%m"),
            "titik": round(pt),
            "l80": round(interval[0.80][0]),
            "u80": round(interval[0.80][1]),
            "l95": round(interval[0.95][0]),
            "u95": round(interval[0.95][1]),
        })

    # 4. Evaluasi Model
    # Nama model sesuai yang ditampilkan di UI
    model_mapping = {
        "naive": "Naive",
        "seasonal_naive": "Seasonal Naive",
        "ETS": "ETS (Holt-Winters)",
        "ETS_tanpa_musim": "ETS (Tanpa Musim)",
        "SARIMAX": "SARIMAX",
        "LightGBM": "LightGBM"
    }

    evaluasi_keseluruhan = [
        {"model": "Naive", "mase": None, "rmse": None, "mae": None, "picp80": None, "picp95": None, "mpiw": None, "winkler": None},
        {"model": "Seasonal Naive", "mase": None, "rmse": None, "mae": None, "picp80": None, "picp95": None, "mpiw": None, "winkler": None},
        {"model": "ETS (Holt-Winters)", "mase": None, "rmse": None, "mae": None, "picp80": None, "picp95": None, "mpiw": None, "winkler": None},
        {"model": "SARIMAX", "mase": None, "rmse": None, "mae": None, "picp80": None, "picp95": None, "mpiw": None, "winkler": None},
        {"model": "LightGBM", "mase": None, "rmse": None, "mae": None, "picp80": None, "picp95": None, "mpiw": None, "winkler": None}
    ]

    evaluasi_pasca_covid = [
        {"model": "Naive", "mase": None},
        {"model": "Seasonal Naive", "mase": None},
        {"model": "ETS (Holt-Winters)", "mase": None},
        {"model": "SARIMAX", "mase": None},
        {"model": "LightGBM", "mase": None}
    ]

    # Baca metrik dari file CSV jika tersedia
    if os.path.exists(PATH_METRIK_BASELINE):
        m_df = pd.read_csv(PATH_METRIK_BASELINE)

        # Hitung interval metrics jika backtest baseline ada
        interval_metrics_semua = {}
        interval_metrics_bersih = {}
        if os.path.exists(PATH_BACKTEST_BASELINE):
            bt_df = pd.read_csv(PATH_BACKTEST_BASELINE)
            for m_key in ["naive", "seasonal_naive", "ETS"]:
                # kalibrasi pada pasca-COVID (bersih == 1)
                sub_cal = bt_df[(bt_df["model"] == m_key) & (bt_df["bersih"] == 1)]
                err_cal = np.abs(sub_cal["y_true"] - sub_cal["y_pred"])
                m_q80 = np.quantile(err_cal, 0.80)
                m_q95 = np.quantile(err_cal, 0.95)

                # semua
                sub_all = bt_df[bt_df["model"] == m_key]
                p80_all = mt.picp(sub_all["y_true"], sub_all["y_pred"] - m_q80, sub_all["y_pred"] + m_q80)
                p95_all = mt.picp(sub_all["y_true"], sub_all["y_pred"] - m_q95, sub_all["y_pred"] + m_q95)
                mp_all = mt.mpiw(sub_all["y_pred"] - m_q95, sub_all["y_pred"] + m_q95)
                wk_all = mt.winkler(sub_all["y_true"], sub_all["y_pred"] - m_q95, sub_all["y_pred"] + m_q95, 0.95)
                interval_metrics_semua[m_key] = {
                    "picp80": round(float(p80_all), 2),
                    "picp95": round(float(p95_all), 2),
                    "mpiw": round(float(mp_all)),
                    "winkler": round(float(wk_all))
                }

        # Isi metrik keseluruhan
        for item in evaluasi_keseluruhan:
            m_name = item["model"]
            # Temukan baris di m_df untuk subset 'semua'
            key = "ETS" if m_name == "ETS (Holt-Winters)" else ("seasonal_naive" if m_name == "Seasonal Naive" else m_name.lower())
            row = m_df[(m_df["subset"] == "semua") & (m_df["model"] == key)]
            if len(row) > 0:
                item["mase"] = round(float(row["MASE"].values[0]), 2)
                item["rmse"] = round(float(row["RMSE"].values[0]))
                item["mae"] = round(float(row["MAE"].values[0]))

            if key in interval_metrics_semua:
                item["picp80"] = interval_metrics_semua[key]["picp80"]
                item["picp95"] = interval_metrics_semua[key]["picp95"]
                item["mpiw"] = interval_metrics_semua[key]["mpiw"]
                item["winkler"] = interval_metrics_semua[key]["winkler"]

        # Isi metrik pasca-COVID (bersih)
        for item in evaluasi_pasca_covid:
            m_name = item["model"]
            key = "ETS" if m_name == "ETS (Holt-Winters)" else ("seasonal_naive" if m_name == "Seasonal Naive" else m_name.lower())
            row = m_df[(m_df["subset"] == "bersih") & (m_df["model"] == key)]
            if len(row) > 0:
                item["mase"] = round(float(row["MASE"].values[0]), 2)

    q_meta = {
        f"{int(round(level * 100))}": {
            str(h): {
                "q_lo": round(q_per_horizon[level][h]["q_lo"], 4),
                "q_hi": round(q_per_horizon[level][h]["q_hi"], 4),
            }
            for h in range(1, horizon_maks + 1)
        }
        for level in KOLOM_INTERVAL_CSV
    }

    data_payload = {
        "_catatan": "Otomatis digenerate dari pipeline Machine Learning tim (src/export_app_data.py). Satuan: ribu penumpang. Format bulan: YYYY-MM.",
        "meta": {
            "sumber": "BPS",
            "satuan": "ribu penumpang",
            "periode_data": periode_data,
            "diperbarui": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z%z"),
            "model_terpilih": "LightGBM",
            "model_catatan": "Sementara mengikuti outputs/prediksi_future_6bln.csv; keputusan model final ditetapkan terpisah.",
            "sumber_file": {
                "forecast_dan_interval": "outputs/prediksi_future_6bln.csv",
                "q_per_horizon": "outputs/q_hat_conformal.csv",
                "data_historis": "data/processed/data_final.csv",
            },
            "q_per_horizon": q_meta,
            "lebaran": lebaran_months
        },
        "ambang_kapasitas": {
            "nilai": ambang_nilai,
            "keterangan": "Parameter sistem (kapasitas operasional representatif KRL Jabodetabek)"
        },
        "historis": historis,
        "forecast": forecast,
        "evaluasi": {
            "keseluruhan": evaluasi_keseluruhan,
            "pasca_covid": evaluasi_pasca_covid
        }
    }

    os.makedirs(os.path.dirname(PATH_OUTPUT_JSON), exist_ok=True)
    with open(PATH_OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(data_payload, f, indent=2, ensure_ascii=False)

    print(f"[OK] data.json berhasil digenerate di: {PATH_OUTPUT_JSON}")
    print(f"     Historis: {len(historis)} bulan ({periode_data})")
    print(f"     Forecast: {len(forecast)} bulan ({forecast[0]['bulan']} s/d {forecast[-1]['bulan']})")
    print(f"     Ambang Kapasitas: {ambang_nilai:,} ribu penumpang")


if __name__ == "__main__":
    generate_dashboard_data()
