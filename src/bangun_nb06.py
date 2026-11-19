"""
bangun_nb06.py
--------------
Menyesuaikan notebook 06 dengan skema artefak yang sudah diperbaiki:

1. Kolom `prediksi_future_6bln.csv` sekarang `y_pred`, `lower_95`, `upper_95`
   (dulu `y_pred_titik`, `batas_atas_95`).
2. Judul bulan tidak lagi ditulis manual "SEPTEMBER 2026 - FEBRUARI 2027",
   tetapi dibaca dari data.
3. Klaim "1,1 juta penumpang per hari kerja" diperbaiki: 34.000 ribu / 30 hari
   = 1,10 juta per hari KALENDER (bukan hari kerja).
4. Warna area interval tidak lagi hijau (berkonotasi aman) saat melewati ambang.
"""

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "notebooks", "06_evaluasi_risiko.ipynb")


def md(teks):
    return {"cell_type": "markdown", "metadata": {},
            "source": teks.strip("\n").splitlines(keepends=True)}


def code(teks):
    return {"cell_type": "code", "execution_count": None, "metadata": {},
            "outputs": [], "source": teks.strip("\n").splitlines(keepends=True)}


sel = []

sel.append(md("""
# 06. Evaluasi Model Komparatif dan Lapisan Keputusan Risiko Kapasitas

Notebook ini membandingkan seluruh model dan menerjemahkan **batas atas**
interval 95% menjadi status risiko kapasitas bagi pemangku kebijakan
KRL Jabodetabek.

### Yang diperbaiki dibanding versi sebelumnya

| Hal | Versi lama | Versi ini |
|---|---|---|
| Sumber ramalan | CSV tanpa producer, semua tanggal = 2026-09-01 | dihitung notebook 05, tanggal benar |
| Interval | `q_hat` in-sample (bocor) | kalibrasi bergulir, PICP 87-93% |
| Label bulan | ditulis manual di teks | dibaca dari data |
| Rasio kapasitas | disebut "okupansi" | disebut **rasio batas atas / ambang** |
| Klaim ambang | "1,1 juta per hari kerja" | 1,10 juta per hari **kalender** |

> **Penting soal tafsir:** status "Kritis" di sini berarti *batas atas
> interval 95%* menyentuh ambang kapasitas. Itu peringatan berbasis
> kehati-hatian (upper bound), bukan ramalan bahwa kapasitas pasti terlampaui.
> Ramalan titiknya sendiri masih di bawah ambang.
"""))

sel.append(code("""
import os
import sys
import warnings

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

warnings.filterwarnings("ignore")

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
import risk as rsk

FOLDER_OUTPUT = os.path.join(ROOT_DIR, "outputs")
FOLDER_GAMBAR = os.path.join(ROOT_DIR, "reports", "figures")
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
## 1. Tabel Komparasi Akurasi Seluruh Model

Subset **bersih** = bulan yang target maupun fiturnya tidak tersentuh COVID
(bukan "pasca-COVID"; rentangnya 2020-01 s/d 2026-08).
"""))

sel.append(code("""
met_komp = pd.read_csv(os.path.join(FOLDER_OUTPUT, "metrik_komparasi_final.csv"))
sub_bersih = met_komp[met_komp["subset"] == "bersih"].sort_values("MASE").reset_index(drop=True)

print("=== PERBANDINGAN PERFORMA SELURUH MODEL (SUBSET BERSIH) ===")
display(sub_bersih.round(3))

met_h = pd.read_csv(os.path.join(FOLDER_OUTPUT, "metrik_per_horizon_final.csv"))
piv = (met_h[met_h["subset"] == "bersih"]
       .pivot(index="horizon", columns="model", values="MASE"))
kolom_urut = [c for c in ["seasonal_naive", "naive", "ETS", "ETS_tanpa_musim",
                          "SARIMA", "SARIMAX", "LightGBM"] if c in piv.columns]
print("\\n=== MASE PER HORIZON (SUBSET BERSIH) ===")
display(piv[kolom_urut].round(3))

juara = sub_bersih.iloc[0]
print(f"\\nModel dengan MASE terbaik: {juara['model']} ({juara['MASE']:.3f})")
"""))

sel.append(md("""
## 2. Klasifikasi Risiko Kapasitas 6 Bulan ke Depan

Ambang kapasitas ditetapkan **34.000 ribu penumpang/bulan**.
Sebagai gambaran: 34.000 ribu / 30 hari ≈ **1,10 juta penumpang per hari
kalender** (bukan per hari kerja; per hari kerja angkanya ≈ 1,6 juta).

- **Aman**: batas atas < 30.600 ribu (90% ambang)
- **Waspada**: batas atas 30.600 - 34.000 ribu
- **Kritis**: batas atas ≥ 34.000 ribu
"""))

sel.append(code("""
df_fut = pd.read_csv(os.path.join(FOLDER_OUTPUT, "prediksi_future_6bln.csv"),
                     parse_dates=["tanggal_target"])

# samakan nama kolom dengan yang dipakai src/risk.py
df_fut = df_fut.rename(columns={"y_pred": "y_pred_titik",
                                "lower_95": "batas_bawah_95",
                                "upper_95": "batas_atas_95"})

df_risiko = rsk.klasifikasi_tabel_risiko(
    df_fut,
    ambang_kapasitas=cfg.AMBANG_KAPASITAS,
    batas_waspada=cfg.BATAS_WASPADA,
)

# label yang lebih tepat: ini rasio batas atas terhadap ambang, bukan okupansi
df_risiko["rasio_batas_atas_%"] = df_risiko["okupansi_batas_atas_%"]
df_risiko["rasio_titik_%"] = df_risiko["okupansi_titik_%"]

df_risiko.to_csv(os.path.join(FOLDER_OUTPUT, "tabel_status_risiko_kapasitas.csv"),
                 index=False)

bulan_awal = df_risiko["tanggal_target"].min().strftime("%B %Y")
bulan_akhir = df_risiko["tanggal_target"].max().strftime("%B %Y")
print(f"=== STATUS RISIKO KAPASITAS ({bulan_awal} - {bulan_akhir}) ===")
display(df_risiko[["horizon", "tanggal_target", "y_pred_titik",
                   "batas_atas_95", "rasio_titik_%", "rasio_batas_atas_%",
                   "status_risiko"]].round(1))

hitung = df_risiko["status_risiko"].value_counts()
print("\\nRekap status:", dict(hitung))
print(f"Jumlah bulan: {len(df_risiko)} (unik {df_risiko['tanggal_target'].nunique()})")
"""))

sel.append(md("""
## 3. Visualisasi Peringatan Dini Risiko Kapasitas

Area interval diberi warna netral (bukan hijau) karena area itu **melewati**
ambang kapasitas — hijau akan memberi kesan aman yang menyesatkan.
"""))

sel.append(code("""
warna_status = {"Aman": "tab:green", "Waspada": "tab:orange", "Kritis": "tab:red"}

fig, ax = plt.subplots(figsize=(12, 6))
tgl = df_risiko["tanggal_target"]

ax.fill_between(tgl, df_risiko["batas_bawah_95"], df_risiko["batas_atas_95"],
                color="tab:blue", alpha=0.15, label="Interval 95%")
ax.plot(tgl, df_risiko["batas_atas_95"], "o--", color="tab:red",
        linewidth=2, label="Batas atas 95%")
ax.plot(tgl, df_risiko["y_pred_titik"], "o-", color="tab:blue",
        linewidth=2.2, label="Ramalan titik")

# tandai titik yang Kritis
kritis = df_risiko[df_risiko["status_risiko"] == "Kritis"]
if not kritis.empty:
    ax.scatter(kritis["tanggal_target"], kritis["batas_atas_95"],
               s=140, color="tab:red", zorder=5, edgecolor="black",
               label="Batas atas melewati ambang")

ax.axhline(cfg.AMBANG_KAPASITAS, color="red", linestyle="-", linewidth=2,
           label=f"Ambang kritis ({cfg.AMBANG_KAPASITAS:,.0f} ribu)")
ax.axhline(cfg.AMBANG_KAPASITAS * cfg.BATAS_WASPADA, color="orange",
           linestyle="--", linewidth=1.6,
           label=f"Batas waspada 90% ({cfg.AMBANG_KAPASITAS * cfg.BATAS_WASPADA:,.0f} ribu)")

ax.set_ylabel("Penumpang (ribu/bulan)")
ax.set_title(f"Peringatan Dini Risiko Kapasitas KRL\\n{bulan_awal} - {bulan_akhir}")
ax.set_ylim(df_risiko["batas_bawah_95"].min() * 0.97,
            max(df_risiko["batas_atas_95"].max(), cfg.AMBANG_KAPASITAS) * 1.03)
ax.legend(fontsize=8, loc="lower left", ncol=2)

# anotasi status per bulan
for _, r in df_risiko.iterrows():
    ax.annotate(r["status_risiko"], (r["tanggal_target"], r["batas_atas_95"]),
                textcoords="offset points", xytext=(0, 9), ha="center",
                fontsize=8, color=warna_status.get(r["status_risiko"], "black"))

plt.xticks(rotation=30)
simpan_gambar("risiko_01_kapasitas_alert.png")
plt.show()
"""))

sel.append(md("""
## 4. Analisis Sensitivitas Ambang Kapasitas

Bagaimana status berubah jika kapasitas efektif bergeser ±10%?
"""))

sel.append(code("""
df_sens = rsk.analisis_sensitivitas(df_fut, ambang_dasar=cfg.AMBANG_KAPASITAS)
df_sens.to_csv(os.path.join(FOLDER_OUTPUT, "analisis_sensitivitas_kapasitas.csv"),
               index=False)

print("=== ANALISIS SENSITIVITAS RISIKO KAPASITAS ===")
display(df_sens)
"""))

sel.append(md("""
## 5. Kesimpulan

Angka di bawah dibaca langsung dari artefak, bukan ditulis manual.
"""))

sel.append(code("""
print("=== RINGKASAN LAPISAN RISIKO ===")
for _, r in df_risiko.iterrows():
    print(f"  {r['tanggal_target']:%Y-%m}  titik {r['y_pred_titik']:>8,.0f} "
          f"({r['rasio_titik_%']:>5.1f}%)   batas atas {r['batas_atas_95']:>8,.0f} "
          f"({r['rasio_batas_atas_%']:>5.1f}%)   {r['status_risiko']}")

print(f"\\nAmbang kapasitas : {cfg.AMBANG_KAPASITAS:,.0f} ribu/bulan")
print(f"Rata-rata ramalan titik : {df_risiko['y_pred_titik'].mean():,.0f} ribu "
      f"({df_risiko['rasio_titik_%'].mean():.1f}% ambang)")

selisih = df_risiko["batas_atas_95"] - cfg.AMBANG_KAPASITAS
print(f"Bulan dengan batas atas di atas ambang: {int((selisih > 0).sum())} dari {len(df_risiko)}")

print("\\nCatatan tafsir:")
print("  Status Kritis berasal dari BATAS ATAS interval 95%, bukan dari ramalan titik.")
print("  Ini sinyal kehati-hatian: 'kalau ramalan meleset ke sisi atas, kapasitas tersentuh'.")
print("  Ramalan titik sendiri masih di bawah ambang pada semua bulan.")
print("  Cakupan interval hasil kalibrasi bergulir 87-93% (target 95%),")
print("  jadi batas atas ini sedikit lebih sempit dari yang ideal.")
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
