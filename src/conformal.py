"""
conformal.py
------------
Kalibrasi interval prediksi yang SAHIH (out-of-sample) dan ASIMETRIS.

Kenapa modul ini ada
--------------------
Versi sebelumnya di notebook 05 menghitung `q_hat` dari SELURUH residual
backtest, lalu mengukur PICP pada residual yang sama. Itu bukan uji conformal:
hasilnya selalu "bagus" karena kunci jawaban dipakai untuk menyusun soal.
PICP 100% pada interval 95% adalah gejala masalah ini, bukan prestasi.

Dua perbaikan di sini:

1. KALIBRASI BERGULIR (rolling calibration)
   Untuk setiap origin o, kuantil residual hanya diambil dari origin yang
   targetnya SUDAH terealisasi sebelum o. Syaratnya o' + h <= o.
   Jadi saat meramal bulan depan, model tidak pernah melihat masa depan.

2. INTERVAL ASIMETRIS
   Residual LightGBM tidak simetris (rata-rata positif ~+500 s/d +1.300),
   artinya model cenderung UNDER-predict. Interval simetris `pred +/- q`
   membuang informasi itu: batas bawah terlalu lebar, batas atas terlalu sempit.
   Di sini batas bawah dan batas atas memakai kuantil residual bertanda
   yang berbeda, sehingga bias ikut terkoreksi secara alami.

Catatan istilah: ini **split conformal dengan residual bertanda**, BUKAN
Conformalized Quantile Regression (CQR). CQR butuh model kuantil terpisah
dan tidak dipakai sebagai jalur utama karena jumlah titik kalibrasi per
horizon terlalu sedikit (27-34) untuk menopang estimasi kuantil 5%.
"""

import numpy as np
import pandas as pd


# ---------------------------------------------------------------
# Kuantil konformal (finite-sample corrected)
# ---------------------------------------------------------------
def _kuantil_konformal(nilai, level, sisi="atas"):
    """
    Kuantil empiris dengan koreksi sampel terbatas ala split conformal.

    level : target cakupan, misalnya 0.80 atau 0.95
    sisi  : 'atas'  -> ambil ekor kanan  (untuk batas atas)
            'bawah' -> ambil ekor kiri   (untuk batas bawah)
            'dua'   -> nilai absolut     (untuk interval simetris)
    """
    nilai = np.asarray(nilai, dtype=float)
    nilai = nilai[~np.isnan(nilai)]
    n = len(nilai)
    if n == 0:
        raise ValueError("Tidak ada residual untuk kalibrasi.")

    if sisi == "dua":
        prob = min(np.ceil((n + 1) * level) / n, 1.0)
        return float(np.quantile(np.abs(nilai), prob))

    # asimetris: bagi alpha ke dua ekor
    alpha = 1.0 - level
    if sisi == "bawah":
        prob = alpha / 2.0
    else:
        prob = 1.0 - alpha / 2.0
    prob = float(np.clip(prob, 0.0, 1.0))
    return float(np.quantile(nilai, prob))


# ---------------------------------------------------------------
# Kalibrasi bergulir
# ---------------------------------------------------------------
def kalibrasi_rolling(hasil_bt, level=0.95, min_kalibrasi=12,
                      mode="asimetris", kolom_model="model",
                      nama_model=None, kolom_bersih="bersih",
                      kalibrasi_hanya_bersih=True):
    """
    Hitung batas interval untuk SETIAP baris backtest memakai residual masa lalu saja.

    Parameter
    ---------
    hasil_bt      : DataFrame hasil backtest. Wajib punya kolom
                    [model, origin, horizon, tanggal_target, y_true, y_pred]
    level         : target cakupan (0.80 / 0.95)
    min_kalibrasi : jumlah residual minimum per horizon sebelum kalibrasi dipakai.
                    Baris yang belum cukup data diberi NaN (bukan 0!) supaya
                    tidak menciptakan interval palsu.
    mode          : 'asimetris' (disarankan) atau 'simetris' (pembanding)
    kalibrasi_hanya_bersih : jika True, residual era COVID tidak dipakai untuk
                    kalibrasi. Ini WAJIB untuk evaluasi subset bersih: residual
                    COVID mencapai ~23.000 (vs ~1.200 saat bersih), sehingga
                    satu-dua titik COVID saja sudah menggelembungkan q_hat
                    sampai interval jadi tak berguna.

    Hasil
    -----
    DataFrame dengan kolom tambahan: lower, upper, q_lo, q_hi, n_kalibrasi
    Baris tanpa kalibrasi tetap ada dengan lower/upper = NaN.
    """
    df = hasil_bt.copy()
    if nama_model is not None:
        df = df[df[kolom_model] == nama_model].copy()

    df["lower"] = np.nan
    df["upper"] = np.nan
    df["q_lo"] = np.nan
    df["q_hi"] = np.nan
    df["n_kalibrasi"] = 0

    # himpunan sumber kalibrasi (bisa dibatasi ke baris bersih)
    if kalibrasi_hanya_bersih and kolom_bersih in df.columns:
        sumber = df[df[kolom_bersih] == 1].copy()
    else:
        sumber = df.copy()
    sumber["residual"] = sumber["y_true"] - sumber["y_pred"]

    for h, grup_h in df.groupby("horizon"):
        grup_h = grup_h.sort_values("origin")
        sumber_h = sumber[sumber["horizon"] == h]

        for idx in grup_h.index:
            o = grup_h.at[idx, "origin"]

            # hanya residual yang targetnya sudah terealisasi sebelum o
            masa_lalu = sumber_h[
                (sumber_h["origin"] + pd.DateOffset(months=int(h))) <= o
            ]
            n = len(masa_lalu)
            if n < min_kalibrasi:
                continue

            r = masa_lalu["residual"].values
            pred = float(grup_h.at[idx, "y_pred"])

            if mode == "simetris":
                q = _kuantil_konformal(r, level, sisi="dua")
                df.at[idx, "lower"] = pred - q
                df.at[idx, "upper"] = pred + q
                df.at[idx, "q_lo"] = q
                df.at[idx, "q_hi"] = q
            elif mode == "bias":
                # Koreksi bias dulu (median residual), lalu interval simetris
                # pada residual terpusat. Lebih stabil daripada membelah alpha
                # ke dua ekor ketika jumlah titik kalibrasi sedikit (~20).
                b = float(np.median(r))
                q = _kuantil_konformal(r - b, level, sisi="dua")
                df.at[idx, "lower"] = pred + b - q
                df.at[idx, "upper"] = pred + b + q
                df.at[idx, "q_lo"] = q
                df.at[idx, "q_hi"] = q
            else:
                q_lo = _kuantil_konformal(r, level, sisi="bawah")
                q_hi = _kuantil_konformal(r, level, sisi="atas")
                df.at[idx, "lower"] = pred + q_lo
                df.at[idx, "upper"] = pred + q_hi
                df.at[idx, "q_lo"] = q_lo
                df.at[idx, "q_hi"] = q_hi

            df.at[idx, "n_kalibrasi"] = n

    return df


def kalibrasi_global(hasil_bt, level=0.95, mode="asimetris",
                     kolom_model="model", nama_model=None):
    """
    Kalibrasi versi LAMA: satu q untuk semua baris (in-sample).

    Disediakan HANYA sebagai pembanding agar selisihnya terlihat di laporan.
    Jangan dipakai untuk mengambil keputusan: PICP-nya bias optimis.
    """
    df = hasil_bt.copy()
    if nama_model is not None:
        df = df[df[kolom_model] == nama_model].copy()

    df["residual"] = df["y_true"] - df["y_pred"]
    df["lower"] = np.nan
    df["upper"] = np.nan

    for h, grup in df.groupby("horizon"):
        r = grup["residual"].values
        if mode == "simetris":
            q = _kuantil_konformal(r, level, sisi="dua")
            df.loc[grup.index, "lower"] = grup["y_pred"] - q
            df.loc[grup.index, "upper"] = grup["y_pred"] + q
        else:
            q_lo = _kuantil_konformal(r, level, sisi="bawah")
            q_hi = _kuantil_konformal(r, level, sisi="atas")
            df.loc[grup.index, "lower"] = grup["y_pred"] + q_lo
            df.loc[grup.index, "upper"] = grup["y_pred"] + q_hi

    return df


# ---------------------------------------------------------------
# Ringkasan kualitas interval
# ---------------------------------------------------------------
def ringkas_interval(df, level, subset_kolom="bersih", kelompok=("horizon",)):
    """
    Tabel PICP / MPIW / Winkler dari baris yang punya interval valid.
    Baris tanpa interval (NaN) otomatis dilewati.
    """
    import metrics as mt

    d = df.dropna(subset=["lower", "upper"]).copy()
    if subset_kolom is not None and subset_kolom in d.columns:
        d = d[d[subset_kolom] == 1]

    baris = []
    kunci = list(kelompok) if isinstance(kelompok, (list, tuple)) else [kelompok]
    for nilai, g in d.groupby(kunci, dropna=False):
        if not isinstance(nilai, tuple):
            nilai = (nilai,)
        rek = dict(zip(kunci, nilai))
        rek.update({
            "n_uji": len(g),
            "n_kalibrasi_median": int(g["n_kalibrasi"].median()) if "n_kalibrasi" in g else 0,
            "PICP_%": round(mt.picp(g["y_true"], g["lower"], g["upper"]) * 100, 1),
            "target_%": round(level * 100, 1),
            "MPIW": round(mt.mpiw(g["lower"], g["upper"]), 1),
            "Winkler": round(mt.winkler(g["y_true"], g["lower"], g["upper"], level), 1),
        })
        baris.append(rek)

    hasil = pd.DataFrame(baris)
    if not hasil.empty:
        hasil["selisih_PICP"] = (hasil["PICP_%"] - hasil["target_%"]).round(1)
    return hasil.sort_values(kunci).reset_index(drop=True)
