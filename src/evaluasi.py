"""
evaluasi.py
-----------
Pipeline evaluasi modelling: backtest -> kalibrasi conformal -> q_hat.

Menggantikan logika di notebook 05 yang menghitung q_hat dan mengukur PICP
pada himpunan residual yang SAMA. Di sini kalibrasi dan evaluasi dipisah:

  - q_hat untuk peramalan nyata diambil dari SELURUH residual bersih
    (semua yang sudah terealisasi).
  - PICP/MPIW/Winkler dilaporkan dari kalibrasi BERGULIR, yaitu tiap baris
    hanya memakai residual yang terealisasi sebelum origin-nya.

Output:
  outputs/backtest_lightgbm.csv        hasil backtest LightGBM
  outputs/q_hat_conformal.csv          kuantil untuk peramalan 6 bulan
  outputs/metrik_interval_conformal.csv ringkasan PICP (rolling & in-sample)
"""

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config as cfg
import conformal as cf
import features as ft
import models as mdl
from backtest import jalankan_backtest, tambah_penanda_covid
from metrics import hitung_skala_mase, mae, rmse, mape, pilih_subset, tabel_metrik
from uji_target import buat_fn_per_hari_kerja

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
F_PROC = os.path.join(ROOT, "data", "processed")
F_OUT = os.path.join(ROOT, "outputs")


def muat_data():
    df = pd.read_csv(os.path.join(F_PROC, "data_final.csv"),
                     parse_dates=["tanggal"]).set_index("tanggal")
    kal = pd.read_csv(os.path.join(F_PROC, "kalender_fitur.csv"),
                      parse_dates=["tanggal"]).set_index("tanggal")
    return df, kal


def jalankan_backtest_semua(df, kal):
    """Backtest LightGBM (varian per hari kerja) + pembanding dari notebook 04."""
    y = df[cfg.KOLOM_TARGET].asfreq("MS")

    print("Backtest LightGBM (target per hari kerja)...")
    fn = buat_fn_per_hari_kerja(cfg.KOLOM_TARGET_ALT)
    bt = jalankan_backtest(y, fn, "LightGBM", cfg.ORIGIN_AWAL_BACKTEST,
                           cfg.HORIZON_MAKS, kal)
    bt = tambah_penanda_covid(bt, kal)

    # gabung dengan baseline & SARIMAX yang sudah ada
    path_lama = os.path.join(F_OUT, "backtest_sarimax_dan_baseline.csv")
    if os.path.exists(path_lama):
        lama = pd.read_csv(path_lama, parse_dates=["origin", "tanggal_target"])
        gabung = pd.concat([lama, bt], ignore_index=True)
    else:
        gabung = bt

    path = os.path.join(F_OUT, "backtest_lightgbm.csv")
    bt.to_csv(path, index=False)
    print(f"  {len(bt)} prediksi -> {path}")
    return gabung, bt


def hitung_q_hat(bt, kolom_bersih="bersih"):
    """
    q_hat final untuk peramalan: kuantil residual dari seluruh baris bersih.

    Ini adalah 'kalibrasi' yang dipakai saat meramal 6 bulan ke depan.
    Evaluasi kejujurannya dilakukan terpisah lewat kalibrasi bergulir.
    """
    d = bt[bt[kolom_bersih] == 1].copy()
    d["residual"] = d["y_true"] - d["y_pred"]

    baris = []
    for level in cfg.LEVEL_INTERVAL:
        for h, g in d.groupby("horizon"):
            r = g["residual"].values
            q_lo = cf._kuantil_konformal(r, level, sisi="bawah")
            q_hi = cf._kuantil_konformal(r, level, sisi="atas")
            # koreksi bias (median) + simetris -> mode yang menang di uji
            b = float(np.median(r))
            q = cf._kuantil_konformal(r - b, level, sisi="dua")
            baris.append({
                "level": level, "horizon": int(h), "n": len(r),
                "bias_median": round(b, 1),
                "q_lo": round(b - q, 1),
                "q_hi": round(b + q, 1),
            })

    hasil = pd.DataFrame(baris)
    path = os.path.join(F_OUT, "q_hat_conformal.csv")
    hasil.to_csv(path, index=False)
    print(f"  q_hat -> {path}")
    return hasil


def evaluasi_interval(bt):
    """Bandingkan kalibrasi bergulir vs in-sample (versi lama)."""
    semua = []
    for level in cfg.LEVEL_INTERVAL:
        for mode, label in [("rolling", "bergulir (sahih)"),
                            ("insample", "in-sample (versi lama)")]:
            if mode == "rolling":
                d = cf.kalibrasi_rolling(bt, level=level, mode="bias")
            else:
                d = cf.kalibrasi_global(bt, level=level, mode="bias")
            t = cf.ringkas_interval(d, level)
            t.insert(0, "level", int(round(level * 100)))
            t.insert(1, "kalibrasi", label)
            semua.append(t)

    hasil = pd.concat(semua, ignore_index=True)
    path = os.path.join(F_OUT, "metrik_interval_conformal.csv")
    hasil.to_csv(path, index=False)
    print(f"  metrik interval -> {path}")
    return hasil


def main():
    df, kal = muat_data()
    y = df[cfg.KOLOM_TARGET].asfreq("MS")
    skala, _ = hitung_skala_mase(y, kal, m=cfg.PERIODE_MUSIM)
    print(f"Skala MASE: {skala:.2f}\n")

    gabung, bt = jalankan_backtest_semua(df, kal)

    print("\nKalibrasi q_hat...")
    q = hitung_q_hat(bt)

    print("\nEvaluasi interval (bergulir vs in-sample)...")
    m = evaluasi_interval(bt)

    # metrik titik semua model
    print("\nMetrik titik semua model...")
    tabel = []
    for nama, sub in [("semua", "semua"), ("non_covid", "non_covid"),
                      ("bersih", "bersih")]:
        d = pilih_subset(gabung, sub)
        t = tabel_metrik(d, skala)
        t.insert(0, "subset", nama)
        tabel.append(t)
    titik = pd.concat(tabel, ignore_index=True)
    path = os.path.join(F_OUT, "metrik_komparasi_final.csv")
    titik.to_csv(path, index=False)
    print(f"  metrik titik -> {path}")

    print("\n" + "=" * 78)
    print("RINGKASAN: metrik titik subset bersih (urut MASE)")
    print("=" * 78)
    b = titik[titik["subset"] == "bersih"].sort_values("MASE")
    print(b.to_string(index=False))

    print("\n" + "=" * 78)
    print("RINGKASAN: PICP interval 95% (subset bersih)")
    print("=" * 78)
    print(m[m["level"] == 95].to_string(index=False))

    return gabung, q, m


if __name__ == "__main__":
    main()
