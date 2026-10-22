"""
features.py
-----------
Membuat fitur untuk model.

Ada dua keluaran:
1. Regressor eksogen untuk SARIMAX   -> buat_exog_sarimax()
2. Tabel fitur untuk LightGBM        -> buat_fitur_lightgbm()

Prinsip utama: TIDAK BOLEH ADA KEBOCORAN DATA (data leakage).
Fitur pada baris dengan titik asal (origin) o hanya boleh memakai
nilai target pada bulan <= o. Nilai kalender bulan target boleh dipakai
karena kalender (hari kerja, Lebaran) sudah diketahui sebelum bulannya tiba.

Istilah:
- origin (o)  : bulan terakhir yang datanya sudah diketahui
- target (t)  : bulan yang ingin diramal, t = o + h bulan
- horizon (h) : jarak peramalan, 1 sampai 6 bulan
"""

import numpy as np
import pandas as pd

# ---------------------------------------------------------------
# Daftar kolom
# ---------------------------------------------------------------
# regressor untuk SARIMAX
KOLOM_EXOG = ["jumlah_hari_kerja", "is_lebaran", "lebaran_lag1",
              "lebaran_lead1", "is_covid"]

# fitur untuk LightGBM
KOLOM_FITUR = [
    # fitur dari masa lalu (sampai origin)
    "y_lag0",          # nilai di bulan origin
    "y_lag1",          # 1 bulan sebelum origin
    "y_lag2",          # 2 bulan sebelum origin
    "y_tahun_lalu",    # nilai bulan yang sama tahun lalu (t - 12)
    "roll_mean_3",     # rata-rata 3 bulan terakhir sampai origin
    "roll_mean_12",    # rata-rata 12 bulan terakhir sampai origin
    # fitur dari kalender bulan target
    "bulan",
    "bulan_sin",
    "bulan_cos",
    "jumlah_hari_kerja",
    "selisih_hari_kerja_vs_tahun_lalu",
    "is_lebaran",
    "lebaran_lag1",
    "lebaran_lead1",
    "is_covid",
]

# kolom pendukung (bukan fitur model, dipakai untuk analisis)
KOLOM_INFO = ["tanggal_target", "y_target", "tercemar_covid"]


# ---------------------------------------------------------------
# BAGIAN 1: FITUR KALENDER
# ---------------------------------------------------------------
def buat_fitur_kalender(kalender):
    """
    Membuat fitur kalender dari tabel kalender.

    kalender : DataFrame dengan index tanggal (awal bulan) dan kolom
               jumlah_hari_kerja, is_lebaran, is_covid.
               Sebaiknya sudah mencakup bulan masa depan, supaya
               fitur lead (bulan depan) di ujung data tidak kosong.

    Fitur Lebaran:
    - is_lebaran    : 1 jika bulan itu adalah bulan Idul Fitri
    - lebaran_lag1  : 1 jika BULAN SEBELUMNYA adalah Lebaran (efek sesudah Lebaran)
    - lebaran_lead1 : 1 jika BULAN DEPAN adalah Lebaran (efek mudik sebelum Lebaran)
    """
    f = pd.DataFrame(index=kalender.index)
    f["jumlah_hari_kerja"] = kalender["jumlah_hari_kerja"]
    f["is_lebaran"] = kalender["is_lebaran"]

    # shift(1)  -> nilai bulan sebelumnya dibawa ke bulan ini
    # shift(-1) -> nilai bulan depan dibawa ke bulan ini
    # Bulan paling ujung tidak punya "bulan depan", diisi 0 (diasumsikan bukan Lebaran).
    f["lebaran_lag1"] = kalender["is_lebaran"].shift(1).fillna(0)
    f["lebaran_lead1"] = kalender["is_lebaran"].shift(-1).fillna(0)

    f["is_covid"] = kalender["is_covid"]

    f = f.astype(int)
    return f


def buat_exog_sarimax(kal_fitur):
    """Ambil kolom regressor untuk SARIMAX (dalam bentuk float)."""
    return kal_fitur[KOLOM_EXOG].astype(float)


# ---------------------------------------------------------------
# BAGIAN 2: FITUR UNTUK LIGHTGBM
# ---------------------------------------------------------------
def buat_fitur_lightgbm(df, kal_fitur, horizon, kolom_target="penumpang_ribu"):
    """
    Membuat tabel fitur untuk 1 horizon.

    df           : DataFrame dengan index tanggal (awal bulan), berisi kolom target
    kal_fitur    : hasil buat_fitur_kalender() (harus mencakup bulan masa depan)
    horizon      : 1 sampai 12 (praktisnya 1 sampai 6)
    kolom_target : nama kolom target (bisa target utama atau target alternatif)

    Hasil: DataFrame dengan index = origin. Tiap baris berarti:
           "kalau saya berada di bulan origin, fitur apa yang saya punya
            untuk meramal bulan origin + horizon?"
    """
    assert 1 <= horizon <= 12, "horizon harus antara 1 dan 12"

    y = df[kolom_target]
    hasil = pd.DataFrame(index=y.index)

    # ----- 1. fitur dari masa lalu (semua sampai origin) -----
    hasil["y_lag0"] = y
    hasil["y_lag1"] = y.shift(1)
    hasil["y_lag2"] = y.shift(2)
    hasil["roll_mean_3"] = y.rolling(3).mean()
    hasil["roll_mean_12"] = y.rolling(12).mean()

    # nilai bulan yang sama tahun lalu dari bulan target: t - 12 = o + h - 12
    # artinya mundur (12 - h) bulan dari origin
    hasil["y_tahun_lalu"] = y.shift(12 - horizon)

    # ----- 2. tanggal bulan target -----
    tgl_target = y.index + pd.DateOffset(months=horizon)
    hasil["tanggal_target"] = tgl_target

    # ----- 3. fitur kalender milik bulan target -----
    kal_target = kal_fitur.reindex(tgl_target)
    kal_target.index = y.index

    # kalender bulan yang sama tahun lalu (untuk membandingkan hari kerja)
    kal_lalu = kal_fitur.reindex(tgl_target - pd.DateOffset(months=12))
    kal_lalu.index = y.index

    hasil["bulan"] = tgl_target.month
    hasil["bulan_sin"] = np.sin(2 * np.pi * tgl_target.month / 12)
    hasil["bulan_cos"] = np.cos(2 * np.pi * tgl_target.month / 12)

    hasil["jumlah_hari_kerja"] = kal_target["jumlah_hari_kerja"]
    hasil["selisih_hari_kerja_vs_tahun_lalu"] = (
        kal_target["jumlah_hari_kerja"] - kal_lalu["jumlah_hari_kerja"]
    )
    hasil["is_lebaran"] = kal_target["is_lebaran"]
    hasil["lebaran_lag1"] = kal_target["lebaran_lag1"]
    hasil["lebaran_lead1"] = kal_target["lebaran_lead1"]
    hasil["is_covid"] = kal_target["is_covid"]

    # ----- 4. nilai target sebenarnya (bulan origin + horizon) -----
    # NaN jika bulan targetnya belum ada datanya (masa depan)
    hasil["y_target"] = y.reindex(tgl_target).values

    # ----- 5. penanda baris yang fiturnya "tercemar" COVID -----
    # Tercemar jika: ada bulan COVID dalam 12 bulan terakhir sampai origin,
    # ATAU bulan yang sama tahun lalu (t - 12) adalah bulan COVID.
    # Ini BUKAN fitur model. Dipakai untuk memisahkan evaluasi pasca-COVID.
    covid_12bln = (kal_fitur["is_covid"].rolling(12, min_periods=1).max()
                   .reindex(y.index).fillna(0).values)
    covid_tahun_lalu = kal_lalu["is_covid"].fillna(0).values
    hasil["tercemar_covid"] = np.maximum(covid_12bln, covid_tahun_lalu).astype(int)

    # urutan kolom
    hasil = hasil[KOLOM_FITUR + KOLOM_INFO]
    return hasil


def pisah_latih_dan_masa_depan(hasil):
    """
    Pisahkan tabel fitur menjadi dua:
    - latih      : fitur lengkap DAN target sudah diketahui (dipakai melatih/backtest)
    - masa_depan : fitur lengkap tapi target belum diketahui (baris untuk meramal)
    Baris yang fiturnya masih kosong (awal data) dibuang.
    """
    fitur_lengkap = hasil[KOLOM_FITUR].notna().all(axis=1)
    punya_target = hasil["y_target"].notna()

    latih = hasil[fitur_lengkap & punya_target].copy()
    masa_depan = hasil[fitur_lengkap & ~punya_target].copy()
    return latih, masa_depan


# ---------------------------------------------------------------
# BAGIAN 3: UJI KEBOCORAN DATA
# ---------------------------------------------------------------
def uji_kebocoran(df, kal_fitur, horizon, origin, kolom_target="penumpang_ribu"):
    """
    Cara uji: ubah semua nilai target SETELAH origin menjadi angka sembarang,
    lalu bangun ulang fitur. Fitur di baris origin harus TIDAK BERUBAH.
    Kalau berubah, berarti ada fitur yang diam-diam memakai data masa depan.

    Hasil: True jika aman, False jika bocor.
    """
    asli = buat_fitur_lightgbm(df, kal_fitur, horizon, kolom_target)
    nilai_asli = asli.loc[origin, KOLOM_FITUR].astype(float).values

    df_rusak = df.copy()
    df_rusak.loc[df_rusak.index > origin, kolom_target] = 999999.0

    rusak = buat_fitur_lightgbm(df_rusak, kal_fitur, horizon, kolom_target)
    nilai_rusak = rusak.loc[origin, KOLOM_FITUR].astype(float).values

    return bool(np.allclose(nilai_asli, nilai_rusak, equal_nan=True))