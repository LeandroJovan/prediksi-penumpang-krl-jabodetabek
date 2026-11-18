"""
kalender.py
-----------
Pembuat kalender eksogen bulanan dari library `holidays`.

Dulu pembuatan kalender hanya ada di notebook generate-data.ipynb dan berhenti
di tahun 2026. Akibatnya bulan Januari-Februari 2027 tidak punya kalender,
sehingga peramalan h=5 dan h=6 memakai kalender yang salah (dan .dropna()
menyembunyikannya).

Modul ini:
1. Membuat kalender untuk rentang tahun yang ditentukan (default 2016-2027).
2. Menyimpan ke CSV dengan nama yang mencerminkan rentang tahunnya.
3. Menyediakan cek_kelengkapan() untuk memastikan horizon peramalan tercakup.

Penanda Lebaran ditulis manual karena library `holidays` hanya memberi label
"Idul Fitri (perkiraan)" dan tanggalnya bisa bergeser; daftar bulan Lebaran
adalah pengetahuan domain yang harus eksplisit.
"""

import os

import numpy as np
import pandas as pd

try:
    import holidays
except ImportError:  # pragma: no cover
    holidays = None

# Bulan jatuhnya Idul Fitri (1 Syawal) per tahun.
# 2013-2026 sesuai notebook asli; 2027 dari perkiraan library holidays.
BULAN_LEBARAN = {
    2013: 8, 2014: 7, 2015: 7, 2016: 7, 2017: 6, 2018: 6, 2019: 6,
    2020: 5, 2021: 5, 2022: 5, 2023: 4, 2024: 4, 2025: 3, 2026: 3,
    2027: 3,
}


def generate_exogenous_calendar(start_year=2016, end_year=2027):
    """Kalender bulanan: hari kerja, libur nasional, penanda Lebaran & COVID."""
    if holidays is None:
        raise ImportError("Library 'holidays' belum terpasang: pip install holidays")

    id_holidays = holidays.Indonesia(years=range(start_year, end_year + 1))

    daily = pd.date_range(start=f"{start_year}-01-01",
                          end=f"{end_year}-12-31", freq="D")
    df_daily = pd.DataFrame({"date": daily})
    df_daily["is_weekday"] = df_daily["date"].dt.dayofweek < 5
    df_daily["is_holiday"] = df_daily["date"].dt.date.isin(id_holidays)
    df_daily["is_workday"] = df_daily["is_weekday"] & (~df_daily["is_holiday"])

    df_daily["year_month"] = df_daily["date"].dt.to_period("M")
    df_monthly = df_daily.groupby("year_month").agg(
        total_hari=("date", "count"),
        jumlah_hari_kerja=("is_workday", "sum"),
        jumlah_libur_nasional_weekday=(
            "is_holiday",
            lambda x: (x & df_daily.loc[x.index, "is_weekday"]).sum(),
        ),
    ).reset_index()
    df_monthly["tanggal"] = df_monthly["year_month"].dt.to_timestamp()
    df_monthly["year_month"] = df_monthly["year_month"].astype(str)

    df_monthly["is_lebaran"] = [
        int(BULAN_LEBARAN.get(t.year) == t.month) for t in df_monthly["tanggal"]
    ]

    df_monthly["is_covid_2020_2022"] = (
        df_monthly["tanggal"].dt.year.isin([2020, 2021, 2022]).astype(int)
    )
    df_monthly["is_covid_mar20_dec22"] = (
        (df_monthly["tanggal"] >= "2020-03-01")
        & (df_monthly["tanggal"] <= "2022-12-31")
    ).astype(int)

    cols = ["year_month", "tanggal", "total_hari", "jumlah_hari_kerja",
            "jumlah_libur_nasional_weekday", "is_lebaran",
            "is_covid_2020_2022", "is_covid_mar20_dec22"]
    return df_monthly[cols].sort_values("tanggal").reset_index(drop=True)


def nama_file(start_year, end_year):
    return f"kalender_eksogen_krl_{start_year}_{end_year}.csv"


def cek_kelengkapan(kal, tanggal_butuh, nama="kalender"):
    """Pastikan semua bulan yang dibutuhkan ada. Gagal keras kalau kurang.

    Ini mengganti pola .dropna() yang dulu menyembunyikan bulan yang hilang.
    """
    tersedia = set(pd.to_datetime(kal["tanggal"]))
    kurang = sorted(set(pd.to_datetime(tanggal_butuh)) - tersedia)
    if kurang:
        daftar = ", ".join(t.strftime("%Y-%m") for t in kurang)
        raise ValueError(
            f"{nama} tidak mencakup {len(kurang)} bulan yang dibutuhkan: {daftar}. "
            f"Perluas rentang tahun kalender."
        )
    return True


if __name__ == "__main__":
    MULAI, AKHIR = 2016, 2027
    df = generate_exogenous_calendar(MULAI, AKHIR)

    folder = os.path.join("data", "raw")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, nama_file(MULAI, AKHIR))
    df.to_csv(path, index=False)

    print(f"Kalender tersimpan: {path}")
    print(f"Baris: {len(df)} | {df['tanggal'].min():%Y-%m} s/d {df['tanggal'].max():%Y-%m}")
    print(f"Bulan Lebaran terdeteksi: {int(df['is_lebaran'].sum())} bulan")
    print("\nCuplikan 2027:")
    print(df[df["tanggal"].dt.year == 2027].to_string(index=False))
