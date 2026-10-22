"""
backtest.py
-----------
Rolling-origin backtest (expanding window).

Cara kerja:
  1. Pilih origin o (bulan terakhir yang datanya dianggap sudah diketahui).
  2. Latih model HANYA dengan data sampai o.
  3. Ramal h = 1 sampai horizon_maks bulan ke depan.
  4. Bandingkan dengan nilai aktual bulan o + h (jika sudah ada).
  5. Geser origin 1 bulan ke depan, ulangi.

Bentuk fungsi model yang boleh dipakai:
    model_fn(y_latih, horizon_maks, kal) -> array berisi horizon_maks prediksi
  y_latih : Series bulanan (index tanggal) sampai origin
  kal     : tabel kalender lengkap (boleh diabaikan oleh baseline;
            dipakai SARIMAX untuk mengambil regressor)
"""

import numpy as np
import pandas as pd


def jalankan_backtest(y, model_fn, nama_model, origin_awal, horizon_maks=6,
                      kal=None, langkah=1, tampil_progres=True):
    """
    Jalankan rolling-origin backtest untuk satu model.

    Hasil: DataFrame (satu baris per kombinasi origin dan horizon)
           kolom: model, origin, horizon, tanggal_target, y_true, y_pred
    """
    y = y.asfreq("MS")
    semua_origin = y.index[y.index >= pd.Timestamp(origin_awal)]
    daftar_origin = semua_origin[::langkah]

    baris = []
    for i, o in enumerate(daftar_origin):
        # origin terakhir tidak punya bulan sesudahnya, lewati
        if (o + pd.DateOffset(months=1)) not in y.index:
            continue

        # data latih: HANYA sampai origin
        y_latih = y.loc[:o]
        assert y_latih.index.max() == o, "Data latih melewati origin!"

        try:
            pred = np.asarray(model_fn(y_latih, horizon_maks, kal), dtype=float)
        except Exception as e:
            print(f"  [{nama_model}] gagal di origin {o.strftime('%Y-%m')}: {e}")
            pred = np.full(horizon_maks, np.nan)

        for h in range(1, horizon_maks + 1):
            t = o + pd.DateOffset(months=h)
            if t not in y.index:
                break   # bulan target belum ada datanya
            baris.append({
                "model": nama_model,
                "origin": o,
                "horizon": h,
                "tanggal_target": t,
                "y_true": y.loc[t],
                "y_pred": pred[h - 1],
            })

        if tampil_progres and (i + 1) % 20 == 0:
            print(f"  [{nama_model}] {i + 1}/{len(daftar_origin)} origin selesai")

    return pd.DataFrame(baris)


def tambah_penanda_covid(hasil, kal):
    """
    Tambahkan kolom penanda untuk memisahkan evaluasi:
      target_covid   : 1 jika bulan target adalah bulan COVID
      tercemar_covid : 1 jika ada bulan COVID dalam 12 bulan sampai origin,
                       ATAU bulan yang sama tahun lalu (t - 12) adalah bulan COVID
      bersih         : 1 jika kedua penanda di atas bernilai 0
    Definisi tercemar_covid sama dengan yang dipakai di features.py.
    """
    hasil = hasil.copy()
    covid = kal["is_covid"].astype(float)

    covid_12bln = covid.rolling(12, min_periods=1).max()   # sampai origin
    covid_lalu = covid.shift(12).fillna(0)                 # bulan t-12 (dilihat di posisi t)

    c_target = covid.reindex(hasil["tanggal_target"]).fillna(0).values
    c_origin = covid_12bln.reindex(hasil["origin"]).fillna(0).values
    c_lalu = covid_lalu.reindex(hasil["tanggal_target"]).fillna(0).values

    hasil["target_covid"] = c_target.astype(int)
    hasil["tercemar_covid"] = np.maximum(c_origin, c_lalu).astype(int)
    hasil["bersih"] = ((hasil["target_covid"] == 0) & (hasil["tercemar_covid"] == 0)).astype(int)
    return hasil


def uji_kebocoran_backtest(y, model_fn, origin_awal, batas, horizon_maks=6,
                           kal=None, langkah=6):
    """
    Uji kebocoran pada backtest.

    Cara: nilai y SETELAH tanggal 'batas' diganti angka sembarang.
    Prediksi untuk origin <= batas harus TIDAK BERUBAH, karena origin tersebut
    seharusnya tidak pernah melihat data setelah dirinya.

    Hasil: True jika aman.
    """
    y = y.asfreq("MS")
    y_rusak = y.copy()
    y_rusak.loc[y_rusak.index > pd.Timestamp(batas)] = 999999.0

    a = jalankan_backtest(y, model_fn, "uji", origin_awal, horizon_maks, kal, langkah, False)
    b = jalankan_backtest(y_rusak, model_fn, "uji", origin_awal, horizon_maks, kal, langkah, False)

    a = a[a["origin"] <= pd.Timestamp(batas)].reset_index(drop=True)
    b = b[b["origin"] <= pd.Timestamp(batas)].reset_index(drop=True)

    return bool(len(a) == len(b) and np.allclose(a["y_pred"], b["y_pred"], equal_nan=True))