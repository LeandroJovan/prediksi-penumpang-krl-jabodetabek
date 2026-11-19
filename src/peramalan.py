"""
peramalan.py
------------
Menghasilkan ramalan 6 bulan ke depan SECARA REPRODUCIBLE.

Kenapa modul ini ada
--------------------
Dulu `outputs/prediksi_future_6bln.csv` tidak diproduksi oleh notebook mana pun:
notebook 05 hanya membacanya (`read_csv`), sementara variabel `future_preds`
dibiarkan kosong. Akibatnya:
  - angka 6 bulan itu tidak bisa dilacak asalnya,
  - semua baris punya `tanggal_target` = 2026-09-01 (salah),
  - grafik peringatan dini runtuh jadi satu titik di sumbu-X.

Modul ini:
1. Melatih model final pada SELURUH data yang tersedia.
2. Mengambil baris fitur masa depan yang benar (bukan `.dropna()` diam-diam).
3. Menerapkan batas interval hasil kalibrasi bergulir.
4. Gagal keras kalau jumlah bulan / tanggal tidak sesuai.
"""

import os

import numpy as np
import pandas as pd

import config as cfg
import features as ft
import models as mdl


def latih_final(df, kal_fitur, kolom_target=cfg.KOLOM_TARGET,
                kolom_fitur=None, params=None):
    """Latih satu model LightGBM per horizon pada seluruh data."""
    if kolom_fitur is None:
        kolom_fitur = ft.KOLOM_FITUR
    models = {}
    for h in range(1, cfg.HORIZON_MAKS + 1):
        df_h = ft.buat_fitur_lightgbm(df, kal_fitur, h, kolom_target)
        df_train = df_h.dropna(subset=["y_target"] + list(kolom_fitur))
        models[h] = mdl._latih_lgbm_per_horizon(df_train, kolom_fitur, params)
    return models


def ramal_6_bulan(df, kal_fitur, origin, q_hat=None, kolom_target=cfg.KOLOM_TARGET,
                  kolom_fitur=None, params=None, per_hari_kerja=True):
    """
    Ramal h = 1..HORIZON_MAKS dari `origin`.

    Parameter
    ---------
    origin        : bulan terakhir yang datanya diketahui (Timestamp awal bulan)
    q_hat         : dict {level: {horizon: (q_lo, q_hi)}} hasil kalibrasi.
                    Kalau None, interval tidak diisi (NaN).
    per_hari_kerja: kalau True, model dilatih pada target per hari kerja
                    lalu dikalikan kembali (varian yang menang di uji A/B).

    Hasil: DataFrame dengan kolom
           horizon, tanggal_target, y_pred, lower_80, upper_80, lower_95, upper_95
    """
    if kolom_fitur is None:
        kolom_fitur = ft.KOLOM_FITUR

    origin = pd.Timestamp(origin).replace(day=1)
    y = df[kolom_target]

    if per_hari_kerja:
        hk_latih = kal_fitur["jumlah_hari_kerja"].reindex(y.index)
        y_latih = y / hk_latih
        kolom_target_latih = "penumpang_per_hari_kerja"
        df_latih = pd.DataFrame({kolom_target_latih: y_latih})
    else:
        kolom_target_latih = kolom_target
        df_latih = df[[kolom_target]]

    baris = []
    for h in range(1, cfg.HORIZON_MAKS + 1):
        df_h = ft.buat_fitur_lightgbm(df_latih, kal_fitur, h, kolom_target_latih)
        df_train = df_h.dropna(subset=["y_target"] + list(kolom_fitur))

        # baris fitur untuk bulan target origin + h
        tgl_target = origin + pd.DateOffset(months=h)
        kandidat = df_h[df_h["tanggal_target"] == tgl_target]
        if kandidat.empty:
            raise ValueError(
                f"Fitur untuk target {tgl_target:%Y-%m} (h={h}) tidak tersedia. "
                f"Periksa cakupan kalender_fitur."
            )
        baris_fitur = kandidat.iloc[[-1]][kolom_fitur]
        if baris_fitur.isna().any(axis=None):
            kolom_na = baris_fitur.columns[baris_fitur.isna().any()].tolist()
            raise ValueError(
                f"Fitur target {tgl_target:%Y-%m} (h={h}) masih NaN: {kolom_na}. "
                f"Kalender kemungkinan belum mencakup bulan ini."
            )

        model = mdl._latih_lgbm_per_horizon(df_train, kolom_fitur, params)
        pred = float(model.predict(baris_fitur.values)[0])

        if per_hari_kerja:
            hk_target = float(kal_fitur.loc[tgl_target, "jumlah_hari_kerja"])
            pred = pred * hk_target

        rek = {"horizon": h, "tanggal_target": tgl_target, "y_pred": pred}

        # interval dari kalibrasi bergulir
        for level in cfg.LEVEL_INTERVAL:
            tag = f"{int(round(level * 100))}"
            if q_hat and level in q_hat and h in q_hat[level]:
                q_lo, q_hi = q_hat[level][h]
                rek[f"lower_{tag}"] = pred + q_lo
                rek[f"upper_{tag}"] = pred + q_hi
            else:
                rek[f"lower_{tag}"] = np.nan
                rek[f"upper_{tag}"] = np.nan

        baris.append(rek)

    hasil = pd.DataFrame(baris)

    # ---- penjagaan: bentuk hasil harus benar ----
    assert len(hasil) == cfg.HORIZON_MAKS, \
        f"Jumlah baris ramalan {len(hasil)}, seharusnya {cfg.HORIZON_MAKS}"
    assert hasil["tanggal_target"].is_unique, "tanggal_target duplikat"
    assert hasil["y_pred"].notna().all(), "Ada ramalan NaN"
    diharap = pd.date_range(origin + pd.DateOffset(months=1),
                            periods=cfg.HORIZON_MAKS, freq="MS")
    assert list(hasil["tanggal_target"]) == list(diharap), \
        "tanggal_target tidak berurutan sesuai horizon"

    return hasil


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    f_proc = os.path.join(root, "data", "processed")
    f_out = os.path.join(root, "outputs")

    df = pd.read_csv(os.path.join(f_proc, "data_final.csv"),
                     parse_dates=["tanggal"]).set_index("tanggal")
    kal = pd.read_csv(os.path.join(f_proc, "kalender_fitur.csv"),
                      parse_dates=["tanggal"]).set_index("tanggal")

    origin = df.index.max()
    print(f"Origin peramalan: {origin:%Y-%m}")
    print(f"Target          : {origin + pd.DateOffset(months=1):%Y-%m} "
          f"s/d {origin + pd.DateOffset(months=cfg.HORIZON_MAKS):%Y-%m}")

    # q_hat dari kalibrasi bergulir (kalau file tersedia)
    q_hat = None
    path_q = os.path.join(f_out, "q_hat_conformal.csv")
    if os.path.exists(path_q):
        q = pd.read_csv(path_q)
        q_hat = {}
        for level, g in q.groupby("level"):
            q_hat[float(level)] = {
                int(r.horizon): (float(r.q_lo), float(r.q_hi))
                for r in g.itertuples()
            }
        print(f"q_hat dimuat dari {path_q}")
    else:
        print("PERINGATAN: q_hat_conformal.csv belum ada, interval akan NaN")

    hasil = ramal_6_bulan(df, kal, origin, q_hat=q_hat)

    os.makedirs(f_out, exist_ok=True)
    path = os.path.join(f_out, "prediksi_future_6bln.csv")
    hasil.to_csv(path, index=False)

    print("\nRamalan 6 bulan:")
    tampil = hasil.copy()
    tampil["tanggal_target"] = tampil["tanggal_target"].dt.strftime("%Y-%m")
    print(tampil.round(0).to_string(index=False))
    print(f"\nTersimpan: {path}")

    return hasil


if __name__ == "__main__":
    main()
