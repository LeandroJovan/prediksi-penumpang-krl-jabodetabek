"""
bangun_nb05.py
--------------
Menyusun ulang notebook 05 agar memakai modul yang sudah diperbaiki
(conformal.py, evaluasi.py, peramalan.py) dan tidak lagi melakukan
kalibrasi in-sample.

Dijalankan sekali; notebook hasilnya tetap bisa dibuka & dijalankan manual.
"""

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "notebooks", "05_lightgbm_conformal.ipynb")


def md(teks):
    return {"cell_type": "markdown", "metadata": {}, "source": teks.strip("\n").splitlines(keepends=True)}


def code(teks):
    return {"cell_type": "code", "execution_count": None, "metadata": {},
            "outputs": [], "source": teks.strip("\n").splitlines(keepends=True)}


sel = []

sel.append(md("""
# 05. Model LightGBM Multi-Horizon dan Kalibrasi Interval

Notebook ini membangun model **LightGBM** multi-horizon dan mengukur
ketidakpastian ramalan dengan **kalibrasi conformal yang sahih**.

### Perubahan penting dibanding versi sebelumnya

| Hal | Versi lama | Versi ini |
|---|---|---|
| Target | total penumpang bulanan | **penumpang per hari kerja**, dikalikan kembali |
| Baris latih | ikut memuat baris dengan fitur NaN | hanya baris dengan fitur **dan** target lengkap |
| Kalibrasi interval | `q_hat` dihitung & diuji pada residual yang sama | **kalibrasi bergulir**: hanya residual yang sudah terealisasi |
| Bentuk interval | simetris | **koreksi bias (median) + simetris** |
| Ramalan 6 bulan | dibaca dari CSV misterius | **dihitung di sini** (`src/peramalan.py`) |
| Cakupan (PICP) | dilaporkan 82-85% & 100% | dilaporkan **apa adanya**: 87-93% untuk target 95% |

> Catatan istilah: metode di sini adalah **split conformal dengan residual
> bertanda**, bukan *Conformalized Quantile Regression* (CQR). CQR tidak dipakai
> karena jumlah titik kalibrasi per horizon hanya ~20, terlalu sedikit untuk
> menopang estimasi kuantil 5%.
"""))

sel.append(code("""
import os
import sys
import warnings

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

warnings.filterwarnings("ignore")

# Deteksi root repository secara dinamis
curr_dir = os.path.abspath(os.getcwd())
candidates = [
    curr_dir,
    os.path.abspath(os.path.join(curr_dir, "..")),
    os.path.abspath(os.path.join(curr_dir, "prediksi-penumpang-krl-jabodetabek")),
]
ROOT_DIR = None
for c in candidates:
    if os.path.exists(os.path.join(c, "src", "config.py")):
        ROOT_DIR = c
        break
if ROOT_DIR is None:
    p = curr_dir
    for _ in range(5):
        if os.path.exists(os.path.join(p, "src", "config.py")):
            ROOT_DIR = p
            break
        p = os.path.dirname(p)
if ROOT_DIR is None:
    ROOT_DIR = os.path.abspath("..")

SRC_DIR = os.path.join(ROOT_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import config as cfg
import conformal as cf
import features as ft
import metrics as mt
import models as mdl
import peramalan as pr
from backtest import jalankan_backtest, tambah_penanda_covid
from uji_target import buat_fn_per_hari_kerja

FOLDER_PROCESSED = os.path.join(ROOT_DIR, "data", "processed")
FOLDER_OUTPUT = os.path.join(ROOT_DIR, "outputs")
FOLDER_GAMBAR = os.path.join(ROOT_DIR, "reports", "figures")
os.makedirs(FOLDER_OUTPUT, exist_ok=True)
os.makedirs(FOLDER_GAMBAR, exist_ok=True)

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 30)
plt.rcParams["figure.figsize"] = (12, 5)
plt.rcParams["axes.grid"] = True
plt.rcParams["grid.alpha"] = 0.3

def simpan_gambar(nama):
    path = os.path.join(FOLDER_GAMBAR, nama)
    plt.savefig(path, dpi=130, bbox_inches="tight")
    print(f"Gambar tersimpan: {path}")
"""))

sel.append(md("""
## 1. Memuat Data

Target utama tetap `penumpang_ribu` (total bulanan) supaya sebanding dengan
ambang kapasitas. Target alternatif `penumpang_per_hari_kerja` dipakai
**di dalam** model untuk memisahkan pengaruh jumlah hari kerja.
"""))

sel.append(code("""
df_final = pd.read_csv(os.path.join(FOLDER_PROCESSED, "data_final.csv"),
                       parse_dates=["tanggal"]).set_index("tanggal")
kal = pd.read_csv(os.path.join(FOLDER_PROCESSED, "kalender_fitur.csv"),
                  parse_dates=["tanggal"]).set_index("tanggal")

y_all = df_final[cfg.KOLOM_TARGET].asfreq("MS")
skala_mase, _ = mt.hitung_skala_mase(y_all, kal, m=cfg.PERIODE_MUSIM)

print(f"Data target   : {len(y_all)} bulan ({y_all.index.min():%Y-%m} s/d {y_all.index.max():%Y-%m})")
print(f"Kalender      : {len(kal)} bulan ({kal.index.min():%Y-%m} s/d {kal.index.max():%Y-%m})")
print(f"Skala MASE    : {skala_mase:.2f} ribu penumpang")
print(f"Origin backtest: {cfg.ORIGIN_AWAL_BACKTEST}")

# penjagaan: kalender harus mencakup horizon peramalan
tgl_butuh = pd.date_range(y_all.index.max() + pd.DateOffset(months=1),
                          periods=cfg.HORIZON_MAKS, freq="MS")
assert set(tgl_butuh).issubset(set(kal.index)), \\
    f"Kalender belum mencakup {[t.strftime('%Y-%m') for t in tgl_butuh if t not in kal.index]}"
print(f"\\nKalender mencakup horizon peramalan: {tgl_butuh[0]:%Y-%m} s/d {tgl_butuh[-1]:%Y-%m} OK")
"""))

sel.append(md("""
## 2. Rolling-Origin Backtest

Model dilatih ulang pada setiap origin dan hanya melihat data sampai origin.
Varian yang dipakai adalah **target per hari kerja** — varian ini menang pada
uji A/B (MASE 0,554 vs 0,663 untuk target total bulanan).
"""))

sel.append(code("""
print("Menjalankan backtest LightGBM (target per hari kerja)...")
fn_lgbm = buat_fn_per_hari_kerja(cfg.KOLOM_TARGET_ALT)
res_lgbm = jalankan_backtest(y_all, fn_lgbm, "LightGBM",
                             cfg.ORIGIN_AWAL_BACKTEST, cfg.HORIZON_MAKS, kal)
res_lgbm = tambah_penanda_covid(res_lgbm, kal)
res_lgbm.to_csv(os.path.join(FOLDER_OUTPUT, "backtest_lightgbm.csv"), index=False)

print(f"\\nSelesai: {len(res_lgbm)} prediksi "
      f"({res_lgbm['origin'].nunique()} origin x {cfg.HORIZON_MAKS} horizon)")
print(f"Prediksi bersih (bebas COVID): {int(res_lgbm['bersih'].sum())}")
display(res_lgbm.head())
"""))

sel.append(md("""
## 3. Evaluasi Akurasi Titik Semua Model

LightGBM dibandingkan dengan SARIMAX, SARIMA, dan baseline dari notebook 04.
"""))

sel.append(code("""
b_sarimax = pd.read_csv(os.path.join(FOLDER_OUTPUT, "backtest_sarimax_dan_baseline.csv"),
                        parse_dates=["origin", "tanggal_target"])
b_all = pd.concat([b_sarimax, res_lgbm], ignore_index=True)
b_all.to_csv(os.path.join(FOLDER_OUTPUT, "backtest_final_semua_model.csv"), index=False)

met_sub = mt.tabel_metrik_per_subset(b_all, skala_mase)
met_sub.to_csv(os.path.join(FOLDER_OUTPUT, "metrik_komparasi_final.csv"), index=False)

print("=== PERBANDINGAN PERFORMA MODEL (SUBSET BERSIH) ===")
display(met_sub[met_sub["subset"] == "bersih"].sort_values("MASE").reset_index(drop=True))

met_h = mt.tabel_metrik_per_subset(b_all, skala_mase, kelompok=("model", "horizon"))
met_h.to_csv(os.path.join(FOLDER_OUTPUT, "metrik_per_horizon_final.csv"), index=False)

piv_mase = (met_h[met_h["subset"] == "bersih"]
            .pivot(index="horizon", columns="model", values="MASE"))
print("\\n=== MASE PER HORIZON (SUBSET BERSIH) ===")
display(piv_mase.round(3))
"""))

sel.append(md("""
## 4. Kalibrasi Interval: Bergulir vs In-Sample

Bagian ini adalah perbaikan terpenting. Versi lama menghitung `q_hat` dari
**seluruh** residual lalu mengukur cakupan pada residual yang sama — hasilnya
selalu 100% karena kunci jawaban dipakai menyusun soal.

Sekarang keduanya dipisah dan dibandingkan berdampingan:

- **bergulir (sahih)**: setiap baris hanya memakai residual yang sudah
  terealisasi sebelum origin-nya. Ini meniru kondisi meramal sungguhan.
- **in-sample (versi lama)**: pembanding untuk menunjukkan besarnya bias.
"""))

sel.append(code("""
tabel_interval = []
for level in cfg.LEVEL_INTERVAL:
    for label, d in [
        ("bergulir (sahih)", cf.kalibrasi_rolling(res_lgbm, level=level, mode="bias")),
        ("in-sample (versi lama)", cf.kalibrasi_global(res_lgbm, level=level, mode="bias")),
    ]:
        t = cf.ringkas_interval(d, level)
        t.insert(0, "level", int(round(level * 100)))
        t.insert(1, "kalibrasi", label)
        tabel_interval.append(t)

tabel_interval = pd.concat(tabel_interval, ignore_index=True)
tabel_interval.to_csv(os.path.join(FOLDER_OUTPUT, "metrik_interval_conformal.csv"), index=False)

print("=== CAKUPAN INTERVAL (SUBSET BERSIH) ===")
display(tabel_interval)

print("\\nBacaan: kolom selisih_PICP negatif berarti cakupan di bawah target.")
print("Angka in-sample yang sempurna (0.0) adalah gejala kebocoran, bukan prestasi.")
"""))

sel.append(code("""
# perbandingan tiga bentuk interval pada level 95%
banding = []
for mode in ["simetris", "bias", "asimetris"]:
    d = cf.kalibrasi_rolling(res_lgbm, level=0.95, mode=mode)
    t = cf.ringkas_interval(d, 0.95)
    t.insert(0, "bentuk_interval", mode)
    banding.append(t)
banding = pd.concat(banding, ignore_index=True)

print("=== PERBANDINGAN BENTUK INTERVAL (95%, BERGULIR) ===")
display(banding[["bentuk_interval", "horizon", "n_uji", "PICP_%",
                 "target_%", "MPIW", "selisih_PICP"]])

ringkas = (banding.groupby("bentuk_interval")
           .apply(lambda g: pd.Series({
               "rata2_selisih_PICP": g["selisih_PICP"].abs().mean(),
               "rata2_MPIW": g["MPIW"].mean()}))
           .sort_values("rata2_selisih_PICP"))
print("\\nRingkasan: makin kecil rata2_selisih_PICP makin dekat ke target nominal")
display(ringkas.round(2))
"""))

sel.append(md("""
## 5. q_hat untuk Peramalan 6 Bulan

`q_hat` final dihitung dari seluruh residual bersih yang sudah terealisasi.
Nilai ini yang dipakai menerjemahkan ramalan titik menjadi batas bawah/atas.
"""))

sel.append(code("""
sub_bersih = res_lgbm[res_lgbm["bersih"] == 1].copy()
sub_bersih["residual"] = sub_bersih["y_true"] - sub_bersih["y_pred"]

print("=== BIAS RESIDUAL PER HORIZON (SUBSET BERSIH) ===")
bias_h = (sub_bersih.groupby("horizon")["residual"]
          .agg(["count", "mean", "median", lambda s: s.abs().mean()])
          .rename(columns={"<lambda_0>": "MAE"}).round(1))
display(bias_h)

q_rows = []
for level in cfg.LEVEL_INTERVAL:
    for h, g in sub_bersih.groupby("horizon"):
        r = g["residual"].values
        b = float(np.median(r))
        q = cf._kuantil_konformal(r - b, level, sisi="dua")
        q_rows.append({"level": level, "horizon": int(h), "n": len(r),
                       "bias_median": round(b, 1),
                       "q_lo": round(b - q, 1), "q_hi": round(b + q, 1)})
q_hat_tabel = pd.DataFrame(q_rows)
q_hat_tabel.to_csv(os.path.join(FOLDER_OUTPUT, "q_hat_conformal.csv"), index=False)

print("\\n=== q_hat (KOREKSI BIAS + SIMETRIS) ===")
display(q_hat_tabel)
"""))

sel.append(md("""
## 6. Visualisasi

Tiga gambar: MASE per horizon, ramalan vs aktual, dan lebar interval per horizon.
"""))

sel.append(code("""
model_urut = ["seasonal_naive", "naive", "ETS", "ETS_tanpa_musim",
              "SARIMA", "SARIMAX", "LightGBM"]
model_ada = [m for m in model_urut if m in piv_mase.columns]

fig, ax = plt.subplots(figsize=(10, 5))
for nama in model_ada:
    lw = 2.5 if nama in ("LightGBM", "SARIMAX") else 1.4
    ax.plot(piv_mase.index, piv_mase[nama], marker="o", label=nama, linewidth=lw)
ax.axhline(1.0, color="red", linestyle="--", alpha=0.7, label="Seasonal Naive (=1.0)")
ax.set_xlabel("Horizon (bulan)")
ax.set_ylabel("MASE")
ax.set_title("MASE per Horizon - Subset Bersih (semakin kecil semakin baik)")
ax.set_xticks(list(piv_mase.index))
ax.legend(fontsize=8, ncol=2)
simpan_gambar("lgbm_01_mase_per_horizon.png")
plt.show()
"""))

sel.append(code("""
# ramalan vs aktual pada origin terakhir yang punya seluruh horizon terealisasi
origin_pilih = (sub_bersih.groupby("origin")["horizon"].nunique()
                .pipe(lambda s: s[s == cfg.HORIZON_MAKS]).index.max())
banding_aktual = sub_bersih[sub_bersih["origin"] == origin_pilih].sort_values("horizon")

fig, ax = plt.subplots(figsize=(11, 5))
ax.plot(banding_aktual["tanggal_target"], banding_aktual["y_true"],
        marker="o", linewidth=2, label="Aktual", color="black")
ax.plot(banding_aktual["tanggal_target"], banding_aktual["y_pred"],
        marker="s", linewidth=2, label="Ramalan LightGBM", color="tab:blue")
ax.set_title(f"Ramalan vs Aktual - origin {origin_pilih:%Y-%m}")
ax.set_ylabel("Penumpang (ribu)")
ax.legend()
simpan_gambar("lgbm_02_prediksi_vs_aktual.png")
plt.show()

print(banding_aktual[["horizon", "tanggal_target", "y_true", "y_pred"]]
      .assign(selisih=lambda d: (d["y_true"] - d["y_pred"]).round(1)).to_string(index=False))
"""))

sel.append(code("""
# lebar interval per horizon: bergulir (sahih) vs in-sample (versi lama)
d_rolling = cf.kalibrasi_rolling(res_lgbm, level=0.95, mode="bias")
d_insample = cf.kalibrasi_global(res_lgbm, level=0.95, mode="bias")
d_rolling = d_rolling.dropna(subset=["lower"])
d_rolling = d_rolling[d_rolling["bersih"] == 1]
d_insample = d_insample[d_insample["bersih"] == 1]

lebar_r = d_rolling.groupby("horizon").apply(lambda g: (g["upper"] - g["lower"]).mean())
lebar_i = d_insample.groupby("horizon").apply(lambda g: (g["upper"] - g["lower"]).mean())

fig, ax = plt.subplots(figsize=(10, 5))
x = np.arange(len(lebar_r))
ax.bar(x - 0.2, lebar_i.values, width=0.4, label="in-sample (versi lama)", color="tab:red", alpha=0.75)
ax.bar(x + 0.2, lebar_r.values, width=0.4, label="bergulir (sahih)", color="tab:green", alpha=0.85)
ax.set_xticks(x)
ax.set_xticklabels([f"h={h}" for h in lebar_r.index])
ax.set_ylabel("Lebar interval 95% (ribu penumpang)")
ax.set_title("Lebar Interval: Versi Lama Membengkak karena Kalibrasi Bocor")
ax.legend()
simpan_gambar("lgbm_04_lebar_interval.png")
plt.show()

print("Rata-rata lebar interval 95%:")
print(pd.DataFrame({"in_sample": lebar_i.round(0), "bergulir": lebar_r.round(0)}).to_string())
"""))

sel.append(md("""
## 7. Feature Importance

Disimpan ke CSV supaya bisa dilacak, bukan hanya ditampilkan di gambar.
"""))

sel.append(code("""
model_final = pr.latih_final(df_final, kal,
                             kolom_target=cfg.KOLOM_TARGET_ALT,
                             kolom_fitur=ft.KOLOM_FITUR)

imp_rows = []
for h, m in model_final.items():
    booster = m.booster_
    gain = booster.feature_importance(importance_type="gain")
    for nama, nilai in zip(ft.KOLOM_FITUR, gain):
        imp_rows.append({"horizon": h, "fitur": nama, "gain": float(nilai)})

imp = pd.DataFrame(imp_rows)
imp["gain_relatif_%"] = (imp.groupby("horizon")["gain"]
                         .transform(lambda s: 100 * s / s.sum()).round(1))
imp.to_csv(os.path.join(FOLDER_OUTPUT, "feature_importance_lgbm.csv"), index=False)

piv_imp = imp.pivot(index="fitur", columns="horizon", values="gain_relatif_%")
print("=== FEATURE IMPORTANCE (% gain, rata-rata semua horizon) ===")
display(piv_imp.assign(rata2=piv_imp.mean(axis=1)).sort_values("rata2", ascending=False).round(1))

fig, ax = plt.subplots(figsize=(10, 6))
rata2 = piv_imp.mean(axis=1).sort_values()
ax.barh(rata2.index, rata2.values, color="steelblue")
ax.set_xlabel("Kontribusi relatif (%)")
ax.set_title("Feature Importance LightGBM (rata-rata h=1..6)")
simpan_gambar("lgbm_03_feature_importance.png")
plt.show()
"""))

sel.append(md("""
## 8. Ramalan 6 Bulan ke Depan

Ramalan dihitung **di sini** oleh `src/peramalan.py`, bukan dibaca dari file
yang tidak jelas asalnya. Origin = bulan terakhir yang datanya tersedia.
"""))

sel.append(code("""
origin_ramal = df_final.index.max()
print(f"Origin peramalan: {origin_ramal:%Y-%m}")

q_hat = {}
for level in cfg.LEVEL_INTERVAL:
    g = q_hat_tabel[q_hat_tabel["level"] == level]
    q_hat[level] = {int(r.horizon): (float(r.q_lo), float(r.q_hi)) for r in g.itertuples()}

future_preds = pr.ramal_6_bulan(df_final, kal, origin_ramal, q_hat=q_hat)
future_preds.to_csv(os.path.join(FOLDER_OUTPUT, "prediksi_future_6bln.csv"), index=False)

tampil = future_preds.copy()
tampil["tanggal_target"] = tampil["tanggal_target"].dt.strftime("%Y-%m")
print("\\n=== RAMALAN 6 BULAN ===")
display(tampil.round(0))
print(f"Bulan unik: {future_preds['tanggal_target'].nunique()} dari {cfg.HORIZON_MAKS} yang diharapkan")
"""))

sel.append(code("""
fig, ax = plt.subplots(figsize=(12, 5))
riwayat = y_all.loc[y_all.index >= "2023-01-01"]
ax.plot(riwayat.index, riwayat.values, marker="o", markersize=3,
        color="black", label="Aktual", linewidth=1.6)
ax.plot(future_preds["tanggal_target"], future_preds["y_pred"],
        marker="s", markersize=6, linewidth=2.2, color="tab:blue",
        label="Ramalan LightGBM")
for kol, warna, alpha in [("80", "tab:blue", 0.18), ("95", "tab:blue", 0.10)]:
    ax.fill_between(future_preds["tanggal_target"],
                    future_preds[f"lower_{kol}"], future_preds[f"upper_{kol}"],
                    color=warna, alpha=alpha, label=f"Interval {kol}%")
ax.axhline(cfg.AMBANG_KAPASITAS, color="red", linestyle="--", linewidth=1.8,
           label=f"Ambang kapasitas ({cfg.AMBANG_KAPASITAS:,.0f} ribu)")
ax.set_ylabel("Penumpang (ribu)")
ax.set_title("Ramalan 6 Bulan ke Depan dengan Interval Kalibrasi Bergulir")
ax.legend(fontsize=8, ncol=2)
simpan_gambar("lgbm_05_ramalan_6bulan.png")
plt.show()
"""))

sel.append(md("""
## 9. Kesimpulan

Angka di bawah dihasilkan otomatis dari artefak, bukan ditulis manual,
supaya selalu konsisten dengan CSV-nya.
"""))

sel.append(code("""
bersih_met = met_sub[met_sub["subset"] == "bersih"].set_index("model")
peringkat = bersih_met["MASE"].sort_values()

print("=== PERINGKAT AKHIR (SUBSET BERSIH, MASE) ===")
for i, (nama, nilai) in enumerate(peringkat.items(), 1):
    tanda = "  <-- model ML" if nama == "LightGBM" else ""
    print(f"  {i}. {nama:18s} MASE = {nilai:.3f}{tanda}")

mase_lgbm = peringkat.get("LightGBM")
mase_sarimax = peringkat.get("SARIMAX")
juara = peringkat.index[0]

print(f"\\nModel terbaik     : {juara} (MASE {peringkat.iloc[0]:.3f})")
print(f"LightGBM          : MASE {mase_lgbm:.3f}")
if mase_sarimax is not None:
    print(f"SARIMAX           : MASE {mase_sarimax:.3f}")

p95 = tabel_interval[(tabel_interval["level"] == 95) &
                     (tabel_interval["kalibrasi"] == "bergulir (sahih)")]
print(f"\\nCakupan interval 95% (bergulir): "
      f"{p95['PICP_%'].min():.1f}% - {p95['PICP_%'].max():.1f}% (target 95%)")
print(f"Rata-rata lebar interval 95%  : {p95['MPIW'].mean():,.0f} ribu penumpang")

print("\\nCatatan kejujuran:")
if mase_sarimax is not None and mase_lgbm > mase_sarimax:
    print("  LightGBM BELUM mengalahkan SARIMAX secara agregat.")
    print("  LightGBM tetap dipakai sebagai model lapisan risiko sesuai keputusan")
    print("  proyek, tetapi tabel evaluasi melaporkan apa adanya.")
else:
    print("  LightGBM mengalahkan SARIMAX secara agregat.")
"""))

nb = {
    "cells": sel,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.11.0"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

with open(PATH, "w", encoding="utf-8") as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)

print(f"Notebook ditulis: {PATH}")
print(f"Jumlah sel: {len(sel)}")
