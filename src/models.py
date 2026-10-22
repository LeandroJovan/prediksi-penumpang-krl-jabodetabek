"""
models.py
---------
Definisi model peramalan.
Semua fungsi model memakai bentuk yang sama supaya bisa dipakai oleh backtest:
    fungsi(y_latih, horizon_maks, kal=None) -> array prediksi sepanjang horizon_maks

Tahap 4 : baseline (naive, seasonal naive, ETS)
Tahap 5 : SARIMAX dan LightGBM akan ditambahkan di file ini
"""

import warnings
import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing


# ---------------------------------------------------------------
# BASELINE 1: NAIVE (nilai terakhir)
# ---------------------------------------------------------------
def prediksi_naive(y_latih, horizon_maks, kal=None):
    """Semua bulan ke depan diprediksi sama dengan nilai bulan terakhir."""
    return np.full(horizon_maks, y_latih.iloc[-1], dtype=float)


# ---------------------------------------------------------------
# BASELINE 2: SEASONAL NAIVE (bulan yang sama tahun lalu)
# ---------------------------------------------------------------
def prediksi_seasonal_naive(y_latih, horizon_maks, kal=None):
    """
    Prediksi bulan o + h = nilai bulan yang sama tahun lalu (o + h - 12).
    Untuk horizon <= 12, bulan acuannya selalu sudah diketahui.
    """
    o = y_latih.index[-1]
    hasil = []
    for h in range(1, horizon_maks + 1):
        bulan_acuan = o + pd.DateOffset(months=h) - pd.DateOffset(months=12)
        hasil.append(y_latih.loc[bulan_acuan])
    return np.array(hasil, dtype=float)


# ---------------------------------------------------------------
# BASELINE 3: ETS (Exponential Smoothing / Holt-Winters)
# ---------------------------------------------------------------
def prediksi_ets(y_latih, horizon_maks, kal=None, musiman=True, damped=True):
    """
    ETS dengan tren additive (damped agar tidak melonjak jauh)
    dan musiman additive periode 12 (bisa dimatikan).
    """
    y_latih = y_latih.asfreq("MS")
    pakai_musiman = "add" if (musiman and len(y_latih) >= 24) else None

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model = ExponentialSmoothing(
            y_latih,
            trend="add",
            damped_trend=damped,
            seasonal=pakai_musiman,
            seasonal_periods=12 if pakai_musiman else None,
            initialization_method="estimated",
        )
        hasil_fit = model.fit()
        return hasil_fit.forecast(horizon_maks).values


def prediksi_ets_tanpa_musim(y_latih, horizon_maks, kal=None):
    """ETS tanpa komponen musiman (hanya level dan tren)."""
    return prediksi_ets(y_latih, horizon_maks, kal, musiman=False)

# ---------------------------------------------------------------
# VERSI "PER HARI KALENDER" UNTUK MODEL APA PUN
# ---------------------------------------------------------------
def per_hari(fungsi_model):
    """
    Membungkus model supaya bekerja pada penumpang per hari kalender.
      1. y_latih dibagi jumlah hari bulannya
      2. model asli meramal angka per hari
      3. hasil dikalikan jumlah hari bulan target
    Jumlah hari tiap bulan sudah pasti, jadi tidak ada kebocoran data.
    """
    def model_baru(y_latih, horizon_maks, kal=None):
        y_hari = y_latih / y_latih.index.days_in_month.values
        pred_hari = np.asarray(fungsi_model(y_hari, horizon_maks, kal), dtype=float)

        o = y_latih.index[-1]
        hari_target = np.array([(o + pd.DateOffset(months=h)).days_in_month
                                for h in range(1, horizon_maks + 1)])
        return pred_hari * hari_target

    return model_baru