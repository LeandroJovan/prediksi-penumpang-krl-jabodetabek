"""
models.py
---------
Definisi model peramalan.
Semua fungsi model memakai bentuk yang sama supaya bisa dipakai oleh backtest:
    fungsi(y_latih, horizon_maks, kal=None) -> array prediksi sepanjang horizon_maks

Tahap 4 : baseline (naive, seasonal naive, ETS)
Tahap 5 : SARIMAX dan LightGBM
"""

import warnings
import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from statsmodels.tsa.statespace.sarimax import SARIMAX

# Kolom regressor eksogen default untuk SARIMAX
KOLOM_EXOG_DEFAULT = [
    "jumlah_hari_kerja",
    "is_lebaran",
    "lebaran_lag1",
    "lebaran_lead1",
    "is_covid",
]


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
        hari_target = np.array([
            (o + pd.DateOffset(months=h)).days_in_month
            for h in range(1, horizon_maks + 1)
        ])
        return pred_hari * hari_target

    return model_baru


# ---------------------------------------------------------------
# SARIMAX & SARIMA
# ---------------------------------------------------------------
def _siapkan_exog(kal, index_latih, index_target, kolom_exog=None):
    """Mempersiapkan matriks regressor eksogen untuk data latih dan masa depan."""
    if kal is None:
        return None, None
    if kolom_exog is None:
        kolom_exog = [c for c in KOLOM_EXOG_DEFAULT if c in kal.columns]
    if not kolom_exog:
        return None, None

    nilai_default = {
        "jumlah_hari_kerja": 21.0,
        "is_lebaran": 0.0,
        "lebaran_lag1": 0.0,
        "lebaran_lead1": 0.0,
        "is_covid": 0.0,
    }
    ex_l = kal.reindex(index_latih)[kolom_exog].fillna(nilai_default).astype(float)
    ex_f = kal.reindex(index_target)[kolom_exog].fillna(nilai_default).astype(float)
    return ex_l, ex_f


def prediksi_sarimax(y_latih, horizon_maks, kal=None, order=(0, 1, 1),
                     seasonal_order=(0, 1, 1, 12), pakai_exog=True, kolom_exog=None):
    """
    SARIMAX dengan regressor eksogen dari kalender.
    Jika pakai_exog=False atau kal=None, berjalan sebagai SARIMA.
    Jika optimasi MLE gagal konvergen atau singular, fallback secara aman ke ETS.
    """
    y_latih = y_latih.asfreq("MS")
    o = y_latih.index[-1]
    target_dates = [o + pd.DateOffset(months=h) for h in range(1, horizon_maks + 1)]

    ex_l, ex_f = None, None
    if pakai_exog and kal is not None:
        ex_l, ex_f = _siapkan_exog(kal, y_latih.index, target_dates, kolom_exog)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            model = SARIMAX(
                y_latih,
                exog=ex_l,
                order=order,
                seasonal_order=seasonal_order,
                enforce_stationarity=False,
                enforce_invertibility=False,
            )
            res = model.fit(disp=False, maxiter=150)
            pred = res.forecast(steps=horizon_maks, exog=ex_f)
            return np.asarray(pred, dtype=float)
        except Exception:
            # Fallback ke ETS jika SARIMAX gagal
            return prediksi_ets(y_latih, horizon_maks, kal)


def prediksi_sarima(y_latih, horizon_maks, kal=None, order=(0, 1, 1),
                    seasonal_order=(0, 1, 1, 12)):
    """SARIMA murni tanpa regressor eksogen (untuk pembanding pengaruh regressor)."""
    return prediksi_sarimax(y_latih, horizon_maks, kal=None, order=order,
                            seasonal_order=seasonal_order, pakai_exog=False)


def ramal_sarimax_interval(y_latih, horizon_maks, kal=None, order=(0, 1, 1),
                           seasonal_order=(0, 1, 1, 12), pakai_exog=True,
                           kolom_exog=None, level=0.95):
    """
    Menghasilkan peramalan titik beserta batas bawah dan batas atas
    pada tingkat kepercayaan 'level' (misalnya 0.95 untuk interval 95%, atau 0.80 untuk 80%).

    Hasil: dict dengan keys: 'y_pred', 'lower', 'upper'
    """
    y_latih = y_latih.asfreq("MS")
    o = y_latih.index[-1]
    target_dates = [o + pd.DateOffset(months=h) for h in range(1, horizon_maks + 1)]

    ex_l, ex_f = None, None
    if pakai_exog and kal is not None:
        ex_l, ex_f = _siapkan_exog(kal, y_latih.index, target_dates, kolom_exog)

    alpha = 1.0 - level
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model = SARIMAX(
            y_latih,
            exog=ex_l,
            order=order,
            seasonal_order=seasonal_order,
            enforce_stationarity=False,
            enforce_invertibility=False,
        )
        res = model.fit(disp=False, maxiter=150)
        fc = res.get_forecast(steps=horizon_maks, exog=ex_f)
        ci = fc.conf_int(alpha=alpha)
        return {
            "y_pred": np.asarray(fc.predicted_mean, dtype=float),
            "lower": np.asarray(ci.iloc[:, 0], dtype=float),
            "upper": np.asarray(ci.iloc[:, 1], dtype=float),
        }
