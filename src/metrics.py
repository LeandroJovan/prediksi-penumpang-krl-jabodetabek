"""
metrics.py
----------
Perhitungan metrik evaluasi.

Metrik titik   : MAE, RMSE, MAPE, MASE
Metrik interval: PICP, MPIW, Winkler score (dipakai di tahap conformal)
"""

import numpy as np
import pandas as pd


# ---------------------------------------------------------------
# METRIK TITIK
# ---------------------------------------------------------------
def mae(y_true, y_pred):
    """Rata-rata selisih absolut."""
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    return np.mean(np.abs(y_true - y_pred))


def rmse(y_true, y_pred):
    """Akar dari rata-rata kuadrat selisih (lebih sensitif pada error besar)."""
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    return np.sqrt(np.mean((y_true - y_pred) ** 2))


def mape(y_true, y_pred):
    """Rata-rata selisih dalam persen. Hanya pendamping, tidak stabil jika y_true kecil."""
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    return np.mean(np.abs((y_true - y_pred) / y_true)) * 100


def hitung_skala_mase(y, kal, m=12):
    """
    Skala untuk MASE = rata-rata |y[t] - y[t-m]| (selisih musiman).

    Hanya pasangan bulan yang KEDUANYA bukan COVID yang dipakai,
    supaya skala tidak membengkak oleh patahan COVID.
    Catatan: skala hanya pembagi (normalisasi), bukan bagian dari prediksi,
    jadi memakai data seluruh periode tidak menimbulkan kebocoran pada prediksi.

    Hasil: (skala, jumlah_pasangan)
    """
    selisih = (y - y.shift(m)).abs()
    covid_t = kal["is_covid"].reindex(y.index)
    covid_lalu = kal["is_covid"].shift(m).reindex(y.index)

    mask = (covid_t == 0) & (covid_lalu == 0) & selisih.notna()
    return selisih[mask].mean(), int(mask.sum())


def mase(y_true, y_pred, skala):
    """
    MASE = MAE / skala.
    < 1 : lebih baik dari seasonal naive
    = 1 : sama dengan seasonal naive
    > 1 : lebih buruk dari seasonal naive
    """
    return mae(y_true, y_pred) / skala


# ---------------------------------------------------------------
# METRIK INTERVAL
# ---------------------------------------------------------------
def picp(y_true, batas_bawah, batas_atas):
    """PICP: proporsi nilai aktual yang jatuh di dalam interval. Targetnya mendekati level nominal."""
    y_true = np.asarray(y_true, dtype=float)
    di_dalam = (y_true >= np.asarray(batas_bawah)) & (y_true <= np.asarray(batas_atas))
    return np.mean(di_dalam)


def mpiw(batas_bawah, batas_atas):
    """MPIW: rata-rata lebar interval."""
    return np.mean(np.asarray(batas_atas, dtype=float) - np.asarray(batas_bawah, dtype=float))


def winkler(y_true, batas_bawah, batas_atas, level):
    """
    Winkler score = lebar interval + penalti jika aktual jatuh di luar interval.
    level : misalnya 0.95 untuk interval 95%.
    """
    y_true = np.asarray(y_true, dtype=float)
    lo = np.asarray(batas_bawah, dtype=float)
    hi = np.asarray(batas_atas, dtype=float)
    alpha = 1 - level

    skor = hi - lo
    skor = skor + (2 / alpha) * (lo - y_true) * (y_true < lo)
    skor = skor + (2 / alpha) * (y_true - hi) * (y_true > hi)
    return np.mean(skor)


# ---------------------------------------------------------------
# PEMILIHAN SUBSET DAN TABEL RINGKASAN
# ---------------------------------------------------------------
def pilih_subset(hasil, nama):
    """
    Memilih baris hasil backtest sesuai subset evaluasi.
      semua     : seluruh baris
      non_covid : bulan target bukan bulan COVID
      bersih    : bulan target dan fiturnya sama sekali tidak tersentuh COVID
    """
    if nama == "semua":
        return hasil
    if nama == "non_covid":
        return hasil[hasil["target_covid"] == 0]
    if nama == "bersih":
        return hasil[hasil["bersih"] == 1]
    raise ValueError("nama subset harus 'semua', 'non_covid', atau 'bersih'")


def tabel_metrik(hasil, skala, kelompok=("model",)):
    """
    Hitung metrik titik per kelompok (misalnya per model, atau per model dan horizon).
    Baris yang prediksinya NaN dibuang dulu.
    """
    hasil = hasil.dropna(subset=["y_pred"])
    daftar = []

    for kunci, g in hasil.groupby(list(kelompok)):
        if not isinstance(kunci, tuple):
            kunci = (kunci,)
        baris = dict(zip(kelompok, kunci))
        baris["n"] = len(g)
        baris["MAE"] = mae(g["y_true"], g["y_pred"])
        baris["RMSE"] = rmse(g["y_true"], g["y_pred"])
        baris["MAPE_%"] = mape(g["y_true"], g["y_pred"])
        baris["MASE"] = mase(g["y_true"], g["y_pred"], skala)
        daftar.append(baris)

    return pd.DataFrame(daftar)


def tabel_metrik_per_subset(hasil, skala, kelompok=("model",),
                            subset=("semua", "non_covid", "bersih")):
    """Gabungkan tabel metrik dari beberapa subset menjadi satu tabel."""
    semua = []
    for nama in subset:
        t = tabel_metrik(pilih_subset(hasil, nama), skala, kelompok)
        t.insert(0, "subset", nama)
        semua.append(t)
    return pd.concat(semua, ignore_index=True)