"""
uji_target.py
-------------
Uji A/B: target TOTAL BULANAN vs target PER HARI KERJA.

Kenapa diuji
------------
Model LightGBM punya bias positif sistematis (+500 s/d +1.300 penumpang)
pada subset bersih: model cenderung meramal terlalu rendah. Salah satu
dugaan penyebabnya adalah target total bulanan mencampur dua hal:
  (a) permintaan penumpang riil
  (b) jumlah hari kerja bulan itu (19-23 hari, bervariasi ~20%)

Kalau kita meramal "penumpang per hari kerja" lalu mengalikannya kembali
dengan jumlah hari kerja bulan target, variasi (b) dikeluarkan dari target
sehingga model tidak perlu mempelajarinya dari fitur.

Cara kerja
----------
Kedua varian memakai:
  - fitur yang sama (KOLOM_FITUR)
  - hyperparameter yang sama
  - rolling-origin backtest yang sama (src/backtest.py)
  - origin dan horizon yang sama
Sehingga perbandingannya apple-to-apple.

Hasil disimpan ke outputs/uji_ab_target.csv
"""

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config as cfg
import features as ft
import models as mdl
from backtest import jalankan_backtest, tambah_penanda_covid
from metrics import hitung_skala_mase, mae, rmse, mape

FOLDER_OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "outputs")


# ---------------------------------------------------------------
# Wrapper model: target per hari kerja, dikembalikan ke skala total
# ---------------------------------------------------------------
def buat_fn_per_hari_kerja(kolom_target_alt):
    """
    Melatih LightGBM pada target per hari kerja, lalu mengalikan hasilnya
    dengan jumlah hari kerja bulan target agar kembali ke skala total.

    Ini pembungkus murni: tidak mengubah isi model LightGBM.
    """
    def fn(y_latih, horizon_maks, kal=None, kolom_fitur=None, params=None):
        if kal is None:
            raise ValueError("kal wajib diisi untuk model LightGBM")
        if kolom_fitur is None:
            kolom_fitur = ft.KOLOM_FITUR
        # y_latih berisi target total; ubah ke per hari kerja
        hk_latih = kal["jumlah_hari_kerja"].reindex(y_latih.index)
        y_alt = y_latih / hk_latih

        df_latih = pd.DataFrame({kolom_target_alt: y_alt})
        hasil = []
        for h in range(1, horizon_maks + 1):
            df_h = ft.buat_fitur_lightgbm(df_latih, kal, h, kolom_target_alt)
            df_train = df_h.dropna(subset=["y_target"] + list(kolom_fitur))
            if len(df_train) < 12:
                hasil.append(mdl.prediksi_ets(y_latih, h)[-1])
                continue

            model = mdl._latih_lgbm_per_horizon(df_train, kolom_fitur, params)
            baris = df_h.iloc[[-1]][kolom_fitur].values
            pred_alt = float(model.predict(baris)[0])

            # kembalikan ke skala total
            tgl_target = df_h["tanggal_target"].iloc[-1]
            hk_target = float(kal.loc[tgl_target, "jumlah_hari_kerja"])
            hasil.append(pred_alt * hk_target)

        return np.array(hasil, dtype=float)

    return fn


def evaluasi(hasil, skala, label):
    """Ringkas metrik pada subset bersih, per horizon dan agregat."""
    bersih = hasil[hasil["bersih"] == 1]
    baris = []
    for h, g in bersih.groupby("horizon"):
        baris.append({
            "varian": label, "horizon": h, "n": len(g),
            "MAE": round(mae(g["y_true"], g["y_pred"]), 1),
            "RMSE": round(rmse(g["y_true"], g["y_pred"]), 1),
            "MAPE": round(mape(g["y_true"], g["y_pred"]), 2),
            "MASE": round(mae(g["y_true"], g["y_pred"]) / skala, 3),
            "bias": round(float((g["y_true"] - g["y_pred"]).mean()), 1),
        })
    baris.append({
        "varian": label, "horizon": "semua", "n": len(bersih),
        "MAE": round(mae(bersih["y_true"], bersih["y_pred"]), 1),
        "RMSE": round(rmse(bersih["y_true"], bersih["y_pred"]), 1),
        "MAPE": round(mape(bersih["y_true"], bersih["y_pred"]), 2),
        "MASE": round(mae(bersih["y_true"], bersih["y_pred"]) / skala, 3),
        "bias": round(float((bersih["y_true"] - bersih["y_pred"]).mean()), 1),
    })
    return pd.DataFrame(baris)


def main():
    print("Menyiapkan data...")
    data = pd.read_csv(os.path.join("data", "processed", "data_final.csv"),
                       parse_dates=["tanggal"]).set_index("tanggal")
    kal = pd.read_csv(os.path.join("data", "processed", "kalender_fitur.csv"),
                      parse_dates=["tanggal"]).set_index("tanggal")
    y = data[cfg.KOLOM_TARGET].asfreq("MS")

    skala, _ = hitung_skala_mase(y, kal, m=cfg.PERIODE_MUSIM)
    print(f"Skala MASE: {skala:.2f}")

    # --- varian A: target total bulanan (baseline sekarang) ---
    print("\n[A] Target total bulanan...")
    fn_a = lambda yl, hm, k: mdl.prediksi_lightgbm(
        yl, hm, k, kolom_target=cfg.KOLOM_TARGET)
    bt_a = jalankan_backtest(y, fn_a, "LightGBM_total",
                             cfg.ORIGIN_AWAL_BACKTEST, cfg.HORIZON_MAKS, kal)

    # --- varian B: target per hari kerja ---
    print("\n[B] Target per hari kerja...")
    fn_b = buat_fn_per_hari_kerja(cfg.KOLOM_TARGET_ALT)
    bt_b = jalankan_backtest(y, fn_b, "LightGBM_per_hari_kerja",
                             cfg.ORIGIN_AWAL_BACKTEST, cfg.HORIZON_MAKS, kal)

    semua = pd.concat([bt_a, bt_b], ignore_index=True)
    semua = tambah_penanda_covid(semua, kal)

    tabel = pd.concat([
        evaluasi(bt_a.assign(bersih=tambah_penanda_covid(bt_a, kal)["bersih"]),
                 skala, "total_bulanan"),
        evaluasi(bt_b.assign(bersih=tambah_penanda_covid(bt_b, kal)["bersih"]),
                 skala, "per_hari_kerja"),
    ], ignore_index=True)

    os.makedirs(FOLDER_OUT, exist_ok=True)
    path = os.path.join(FOLDER_OUT, "uji_ab_target.csv")
    tabel.to_csv(path, index=False)

    print("\n" + "=" * 74)
    print("HASIL UJI A/B (subset bersih)")
    print("=" * 74)
    print(tabel.to_string(index=False))

    # kesimpulan otomatis
    agg = tabel[tabel["horizon"] == "semua"].set_index("varian")
    menang = agg["MASE"].idxmin()
    print(f"\nMASE agregat terbaik: {menang} ({agg.loc[menang, 'MASE']})")
    print(f"Selisih MASE: {agg.loc['total_bulanan','MASE'] - agg.loc['per_hari_kerja','MASE']:+.3f}")
    print(f"Selisih bias: {agg.loc['per_hari_kerja','bias'] - agg.loc['total_bulanan','bias']:+.1f}")
    print(f"\nTersimpan: {path}")

    return tabel


if __name__ == "__main__":
    main()
