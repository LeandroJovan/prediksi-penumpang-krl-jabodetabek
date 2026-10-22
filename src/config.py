"""
config.py
---------
Parameter proyek dikumpulkan di sini supaya tidak tersebar di banyak file.
Kalau mau ubah pengaturan, ubah di file ini saja.
"""

# ---------- Periode COVID ----------
COVID_MULAI = "2020-03-01"
COVID_AKHIR = "2022-12-31"
PASCA_COVID = "2023-01-01"

# ---------- Peramalan ----------
HORIZON_MAKS = 6                 # meramal 1 sampai 6 bulan ke depan
LEVEL_INTERVAL = [0.80, 0.95]    # level interval prediksi

# ---------- Target ----------
KOLOM_TARGET = "penumpang_ribu"                  # target utama (ribu orang)
KOLOM_TARGET_ALT = "penumpang_per_hari"    # target alternatif (dinormalisasi hari kerja)

# ---------- Kapasitas (diisi pada fase lapisan keputusan) ----------
AMBANG_KAPASITAS = None          # ribu penumpang per bulan, belum ditentukan
BATAS_WASPADA = 0.90             # waspada jika batas atas >= 90% ambang

# ---------- Backtest ----------
ORIGIN_AWAL_BACKTEST = "2019-12-01"   # origin pertama (48 bulan data latih: 2016-01 s/d 2019-12)
PERIODE_MUSIM = 12                    # musiman bulanan