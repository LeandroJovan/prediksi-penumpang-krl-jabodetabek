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
import numpy as np
import pandas as pd

# Tambahkan direktori src ke path
DIR_SRC = os.path.dirname(os.path.abspath(__file__))
DIR_ROOT = os.path.dirname(DIR_SRC)
sys.path.append(DIR_SRC)

import config as cfg
import models as mdl
import metrics as mt

PATH_DATA_FINAL = os.path.join(DIR_ROOT, "data", "processed", "data_final.csv")
PATH_METRIK_BASELINE = os.path.join(DIR_ROOT, "outputs", "metrik_baseline.csv")
PATH_BACKTEST_BASELINE = os.path.join(DIR_ROOT, "outputs", "backtest_baseline.csv")
PATH_OUTPUT_JSON = os.path.join(DIR_ROOT, "frontend", "data", "data.json")


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

    # 3. Model Peramalan & Conformal Prediction (Interval 80% & 95%)
    # Menggunakan deret target penuh
    y_series = df.set_index("tanggal")["penumpang_ribu"].asfreq("MS")
    horizon_maks = getattr(cfg, "HORIZON_MAKS", 6)

    # Model terpilih: ETS (Holt-Winters)
    pred_titik = mdl.prediksi_ets(y_series, horizon_maks)

    # Hitung conformal residual quantiles dari data backtest bersih (pasca-COVID)
    q80 = 2865.0
    q95 = 3847.0

    if os.path.exists(PATH_BACKTEST_BASELINE):
        bt_df = pd.read_csv(PATH_BACKTEST_BASELINE)
        sub_cal = bt_df[(bt_df["model"] == "ETS") & (bt_df["bersih"] == 1)]
        if len(sub_cal) > 0:
            err = np.abs(sub_cal["y_true"] - sub_cal["y_pred"])
            q80 = float(np.quantile(err, 0.80))
            q95 = float(np.quantile(err, 0.95))

    # Bentuk array forecast untuk 6 bulan ke depan
    origin_terakhir = y_series.index[-1]
    forecast = []
    for h in range(1, horizon_maks + 1):
        target_date = origin_terakhir + pd.DateOffset(months=h)
        target_str = target_date.strftime("%Y-%m")
        pt = float(pred_titik[h - 1])
        forecast.append({
            "bulan": target_str,
            "titik": round(pt),
            "l80": max(0, round(pt - q80)),
            "u80": round(pt + q80),
            "l95": max(0, round(pt - q95)),
            "u95": round(pt + q95)
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

    data_payload = {
        "_catatan": "Otomatis digenerate dari pipeline Machine Learning tim (src/export_app_data.py). Satuan: ribu penumpang. Format bulan: YYYY-MM.",
        "meta": {
            "sumber": "BPS",
            "satuan": "ribu penumpang",
            "periode_data": periode_data,
            "diperbarui": "Agustus 2026",
            "model_terpilih": "ETS (Holt-Winters)",
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
