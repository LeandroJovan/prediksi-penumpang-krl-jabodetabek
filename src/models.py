"""
models.py
---------
Definisi model peramalan.
Semua fungsi model memakai bentuk yang sama supaya bisa dipakai oleh backtest:
    fungsi(y_latih, horizon_maks, kal=None) -> array prediksi sepanjang horizon_maks

Tahap 4 : baseline (naive, seasonal naive, ETS)
Tahap 5 : SARIMAX dan LightGBM + Conformalized Quantile Regression (CQR)
"""

import warnings
import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from statsmodels.tsa.statespace.sarimax import SARIMAX
import lightgbm as lgb
from features import buat_fitur_lightgbm, KOLOM_FITUR

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



# ---------------------------------------------------------------
# LIGHTGBM — DIRECT MULTI-HORIZON STRATEGY
# ---------------------------------------------------------------
# Parameter default LightGBM (titik)
LGBM_PARAMS_DEFAULT = {
    "objective": "regression",
    "metric": "mae",
    "n_estimators": 300,
    "learning_rate": 0.05,
    "num_leaves": 31,
    "min_child_samples": 5,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "reg_alpha": 0.1,
    "reg_lambda": 0.1,
    "random_state": 42,
    "verbose": -1,
}

# Parameter LightGBM untuk quantile regression
LGBM_PARAMS_QUANTILE = {
    "objective": "quantile",
    "metric": "quantile",
    "n_estimators": 300,
    "learning_rate": 0.05,
    "num_leaves": 31,
    "min_child_samples": 5,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "reg_alpha": 0.1,
    "reg_lambda": 0.1,
    "random_state": 42,
    "verbose": -1,
}


def _latih_lgbm_per_horizon(df_fitur_h, kolom_fitur=None, params=None):
    """
    Melatih satu model LightGBM untuk 1 horizon.

    df_fitur_h : DataFrame dari buat_fitur_lightgbm() untuk 1 horizon.
                 Baris dengan y_target=NaN dibuang.
    kolom_fitur: list kolom fitur. Default: KOLOM_FITUR dari features.py
    params     : dict parameter LightGBM

    Return: model LightGBM yang sudah dilatih
    """
    if kolom_fitur is None:
        kolom_fitur = KOLOM_FITUR
    if params is None:
        params = LGBM_PARAMS_DEFAULT

    df_train = df_fitur_h.dropna(subset=["y_target"])
    X = df_train[kolom_fitur].values
    y = df_train["y_target"].values

    model = lgb.LGBMRegressor(**params)
    model.fit(X, y)
    return model


def latih_semua_horizon(df, kal_fitur, kolom_target="penumpang_ribu",
                        kolom_fitur=None, params=None):
    """
    Melatih 6 model LightGBM (satu per horizon h=1..6) menggunakan
    SELURUH data historis yang tersedia (bukan rolling backtest).
    Dipakai untuk menghasilkan prakiraan masa depan final.

    Return: dict {horizon: model}
    """
    from features import buat_fitur_lightgbm
    if kolom_fitur is None:
        kolom_fitur = KOLOM_FITUR

    models = {}
    for h in range(1, 7):
        df_h = buat_fitur_lightgbm(df, kal_fitur, h, kolom_target)
        models[h] = _latih_lgbm_per_horizon(df_h, kolom_fitur, params)
    return models


def prediksi_lightgbm(y_latih, horizon_maks, kal=None,
                      kolom_fitur=None, params=None, kolom_target="penumpang_ribu"):
    """
    Fungsi wrapper LightGBM yang kompatibel dengan antarmuka backtest.

    Strategy: DIRECT multi-horizon — satu model dilatih per horizon,
    masing-masing meramal h bulan ke depan dari origin.
    Setiap model hanya melihat data sampai y_latih (origin o).

    Catatan: kal WAJIB diisi (dipakai untuk fitur kalender bulan target).
    """
    from features import buat_fitur_lightgbm
    if kolom_fitur is None:
        kolom_fitur = KOLOM_FITUR

    df_latih = pd.DataFrame({"penumpang_ribu": y_latih})

    prediksi_semua = []
    for h in range(1, horizon_maks + 1):
        df_h = buat_fitur_lightgbm(df_latih, kal, h, kolom_target)
        df_train = df_h.dropna(subset=["y_target"])

        if len(df_train) < 12:
            # Terlalu sedikit data latih, fallback ke ETS
            pred = prediksi_ets(y_latih, h)[-1]
            prediksi_semua.append(pred)
            continue

        mdl = _latih_lgbm_per_horizon(df_train, kolom_fitur, params)

        # Baris prediksi: baris terakhir df_h (baris origin, target = o+h)
        baris_pred = df_h.iloc[[-1]][kolom_fitur].values
        pred = float(mdl.predict(baris_pred)[0])
        prediksi_semua.append(pred)

    return np.array(prediksi_semua, dtype=float)


def prediksi_lightgbm_quantile(y_latih, horizon_maks, kal=None,
                               kolom_fitur=None, alpha_lo=0.10, alpha_hi=0.90,
                               kolom_target="penumpang_ribu"):
    """
    LightGBM Quantile Regression — melatih 3 model per horizon:
      - kuantil bawah (alpha_lo) -> batas bawah mentah
      - median (0.50)            -> prediksi titik
      - kuantil atas (alpha_hi)  -> batas atas mentah

    Return: dict {h: {"y_pred", "lower_raw", "upper_raw"}}
    """
    from features import buat_fitur_lightgbm
    if kolom_fitur is None:
        kolom_fitur = KOLOM_FITUR

    df_latih = pd.DataFrame({"penumpang_ribu": y_latih})
    hasil = {}

    for h in range(1, horizon_maks + 1):
        df_h = buat_fitur_lightgbm(df_latih, kal, h, kolom_target)
        df_train = df_h.dropna(subset=["y_target"])
        baris_pred = df_h.iloc[[-1]][kolom_fitur].values

        preds = {}
        for nama, alpha in [("lower_raw", alpha_lo),
                             ("y_pred", 0.50),
                             ("upper_raw", alpha_hi)]:
            p = {**LGBM_PARAMS_QUANTILE, "alpha": alpha}
            mdl = lgb.LGBMRegressor(**p)
            mdl.fit(df_train[kolom_fitur].values, df_train["y_target"].values)
            preds[nama] = float(mdl.predict(baris_pred)[0])

        hasil[h] = preds

    return hasil


# ---------------------------------------------------------------
# CONFORMALIZED QUANTILE REGRESSION (CQR)
# ---------------------------------------------------------------
def hitung_residual_backtest(hasil_bt, nama_model="LGBM"):
    """
    Mengekstrak residual out-of-sample dari DataFrame hasil backtest
    untuk dipakai sebagai data kalibrasi conformal prediction.

    hasil_bt : DataFrame hasil bt.jalankan_backtest()
    Return   : DataFrame dengan kolom [horizon, residual_abs]
               (subset non-NaN saja)
    """
    df = hasil_bt[hasil_bt["model"] == nama_model].dropna(subset=["y_pred"]).copy()
    df["residual_abs"] = (df["y_true"] - df["y_pred"]).abs()
    return df[["origin", "horizon", "tanggal_target", "y_true", "y_pred",
               "residual_abs", "bersih", "tercemar_covid"]]


def hitung_kuantil_konformal(residuals_df, level=0.90, subset="bersih"):
    """
    Menghitung kuantil konformal (q_hat) per horizon.

    residuals_df : output dari hitung_residual_backtest()
    level        : tingkat cakupan yang diinginkan (mis. 0.80 atau 0.95)
    subset       : 'bersih', 'non_covid', atau 'semua'

    Return: dict {horizon: q_hat}
    """
    if subset == "bersih":
        df = residuals_df[residuals_df["bersih"] == 1]
    elif subset == "non_covid":
        df = residuals_df[residuals_df["tercemar_covid"] == 0]
    else:
        df = residuals_df

    q_hat = {}
    for h in range(1, 7):
        res_h = df[df["horizon"] == h]["residual_abs"]
        if len(res_h) == 0:
            q_hat[h] = np.nan
            continue
        # Kuantil konformal: np.ceil((n+1)*level)/n-quantile
        n = len(res_h)
        quantile_level = min(np.ceil((n + 1) * level) / n, 1.0)
        q_hat[h] = float(np.quantile(res_h, quantile_level))

    return q_hat


def terapkan_cqr(prediksi_median, q_hat_lo, q_hat_hi):
    """
    Menerapkan CQR: interval akhir = [pred - q_hat_lo, pred + q_hat_hi]

    prediksi_median : array panjang horizon_maks
    q_hat_lo        : dict {horizon: q_lo} — koreksi ke bawah
    q_hat_hi        : dict {horizon: q_hi} — koreksi ke atas

    Return: dict {"y_pred", "lower", "upper"}
    """
    y_pred = np.asarray(prediksi_median, dtype=float)
    lower = np.array([y_pred[h - 1] - q_hat_lo.get(h, 0) for h in range(1, len(y_pred) + 1)])
    upper = np.array([y_pred[h - 1] + q_hat_hi.get(h, 0) for h in range(1, len(y_pred) + 1)])
    return {"y_pred": y_pred, "lower": lower, "upper": upper}
