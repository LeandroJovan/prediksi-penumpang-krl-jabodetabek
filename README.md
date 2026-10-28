# Prediksi Permintaan Penumpang KRL Jabodetabek Berbasis Time Series dengan Interval Prediksi

Proyek Sistem Cerdas, Program Studi Sains Data Terapan, Politeknik Elektronika Negeri Surabaya (PENS).

Proyek ini meramalkan jumlah penumpang KRL Jabodetabek per bulan, lengkap dengan
**batas bawah dan batas atas prediksi** (interval 80% dan 95%), lalu mengubah batas atas
tersebut menjadi **status risiko kapasitas** (aman, waspada, kritis).

---

## Daftar Isi

1. [Latar Belakang](#1-latar-belakang)
2. [Permasalahan](#2-permasalahan)
3. [Tujuan](#3-tujuan)
4. [Data](#4-data)
5. [Workflow Kerja](#5-workflow-kerja)
6. [Metode](#6-metode)
7. [Evaluasi](#7-evaluasi)
8. [Struktur Repositori](#8-struktur-repositori)
9. [Cara Menjalankan](#9-cara-menjalankan)
10. [Status Pengerjaan](#10-status-pengerjaan)
11. [Keterbatasan](#11-keterbatasan)
12. [Referensi](#12-referensi)

---

## 1. Latar Belakang

KRL Commuter Line adalah tulang punggung transportasi harian di Jabodetabek. Mayoritas
penggunanya adalah pekerja dan pelajar, sehingga kepadatan KRL berkaitan langsung dengan
produktivitas, waktu tempuh, dan keselamatan penumpang.

Beberapa fakta yang melatarbelakangi proyek ini:

- Menurut laporan KAI, jumlah perjalanan KRL naik dari sekitar 168 juta (2021) menjadi
  sekitar 349 juta (2025), dan rata-rata sekitar 1,05 juta per hari kerja pada semester I 2026.
- Okupansi jam sibuk dilaporkan mencapai 128–161% di beberapa lintas.
- Infrastruktur (persinyalan, gardu listrik, armada, dan headway) berkembang jauh lebih
  lambat daripada pertumbuhan permintaan.
- Data BPS Januari–Mei 2026 berkisar 27,8–30,6 juta penumpang per bulan, mirip level
  Juli 2018 (sekitar 29,1 juta). Jika definisinya sebanding, jumlah penumpang tercatat
  cenderung mendatar. Dugaannya adalah **keterbatasan kapasitas**, bukan turunnya
  permintaan. Ini hipotesis yang diuji dalam proyek ini, bukan kesimpulan.

## 2. Permasalahan

1. Keputusan penambahan layanan sulit dipertanggungjawabkan karena tidak ada ukuran
   **ketidakpastian** permintaan. Prediksi satu angka tidak cukup untuk perencanaan kapasitas.
2. Pola permintaan dipengaruhi tren, musiman, Lebaran, jumlah hari kerja, dan COVID,
   sehingga perlu model yang mempelajari faktor-faktor ini dari data.
3. Penumpang yang tercatat belum tentu sama dengan permintaan sebenarnya, karena data
   bisa tertahan oleh kapasitas.

## 3. Tujuan

1. Meramalkan jumlah penumpang KRL Jabodetabek bulanan beberapa bulan ke depan
   secara akurat.
2. Menghasilkan **interval prediksi 80% dan 95%** dengan cakupan (coverage) yang terukur.
3. Menerjemahkan batas atas prediksi menjadi **peringatan risiko kelebihan kapasitas**
   sebagai dukungan keputusan bagi operator dan pemerintah.
4. Menguji secara empiris apakah penumpang pasca-COVID benar-benar mendatar.

**Klaim "cerdas" hanya sah jika model utama terbukti mengalahkan baseline** dalam akurasi
titik dan cakupan interval, berdasarkan backtest.

## 4. Data

| Data | Sumber | Isi |
|---|---|---|
| Jumlah penumpang kereta api (variabel target) | BPS (sumber asli: PT KAI dan KAI Commuter) | 11 file CSV, satu per tahun (2016–2026), hanya kategori **Jabodetabek** dipakai |
| Kalender eksogen (variabel prediktor) | Dibangkitkan dengan library `holidays` | Hari kerja, libur nasional, penanda Lebaran, penanda COVID |

Ringkasan:

- Granularitas: **bulanan**, tingkat sistem agregat (tanpa data per stasiun atau lintas).
- Satuan target: **ribu orang**.
- Rentang: Januari 2016 sampai bulan terakhir yang dirilis BPS.
- Hanya satu sumber (BPS) yang dipakai sebagai seri utama, karena angka BPS dan KAI berbeda.
- Penanda COVID: Maret 2020 sampai Desember 2022.

Dokumentasi lengkap (kamus data, catatan kualitas, log perubahan) ada di
[`data/README.md`](data/README.md).

## 5. Workflow Kerja

```
┌─────────────────────────────────────────────────────────────────────┐
│ 1. Gabung data   →  2. EDA   →  3. Fitur   →  4. Backtest & baseline │
│                                                                     │
│ 5. Model utama (SARIMAX, LightGBM)  →  6. Interval conformal        │
│                                                                     │
│ 7. Evaluasi & pilih model  →  8. Lapisan keputusan  →  9. Dashboard │
└─────────────────────────────────────────────────────────────────────┘
```

| Tahap | Notebook / modul | Yang dikerjakan | Output |
|---|---|---|---|
| 1. Persiapan data | `01_data_prep.ipynb`, `src/data_prep.py` | Gabung 11 file BPS (wide menjadi long), ambil baris Jabodetabek, validasi total 12 bulan terhadap kolom `Tahunan`, bersihkan kalender, gabung target dan kalender | `data/processed/data_final.csv`, `kalender_future.csv`, `validasi_tahunan.csv` |
| 2. EDA | `02_eda.ipynb` | Tren, dampak COVID, musiman (STL, indeks musiman), efek Lebaran dan hari kerja, uji stasioneritas (ADF, KPSS), ACF/PACF, uji hipotesis "mendatar" | Grafik di `reports/figures/`, temuan tertulis |
| 3. Rekayasa fitur | `03_features.ipynb`, `src/features.py` | Lag target, rolling mean (dengan `shift(1)` agar tidak bocor), fitur bulan, Lebaran lag/lead, penanda COVID | Tabel fitur siap model |
| 4. Backtest dan baseline | `src/backtest.py`, `04_baseline_sarimax.ipynb` | Rancang rolling-origin backtest, bangun baseline (seasonal naive dan ETS) | Kerangka evaluasi, skor baseline |
| 5. Model utama | `04_baseline_sarimax.ipynb`, `05_lightgbm_conformal.ipynb`, `src/models.py` | SARIMAX dengan regressor, LightGBM dengan fitur lag dan quantile regression | Prediksi titik per fold dan horizon |
| 6. Interval prediksi | `05_lightgbm_conformal.ipynb` | Conformal prediction dari residual backtest (interval 80% dan 95%) | Batas bawah dan atas |
| 7. Evaluasi | `src/metrics.py`, `06_evaluasi_risiko.ipynb` | Bandingkan semua model dengan MASE, PICP, MPIW, Winkler | Tabel perbandingan, model terpilih |
| 8. Lapisan keputusan | `src/risk.py`, `06_evaluasi_risiko.ipynb` | Bandingkan batas atas dengan ambang kapasitas, tentukan status, analisis sensitivitas | Tabel prediksi dan status risiko |
| 9. Aplikasi | `app/` | Dashboard interaktif (Streamlit) | Dashboard |

## 6. Metode

**Baseline**
- Seasonal naive: prediksi bulan ini sama dengan bulan yang sama tahun lalu.
- ETS (Holt-Winters) dengan musiman 12.

**Model utama**
- **SARIMAX** dengan regressor kalender (hari kerja, Lebaran, COVID).
- **LightGBM** dengan fitur lag dan rolling, serta quantile regression.

**Penanganan COVID** (2020–2022 adalah patahan struktural)
- Penanda COVID sebagai regressor.
- Pembandingan dengan data latih yang dipotong mulai 2023.
- Hasil evaluasi dilaporkan dua kali: seluruh periode dan hanya pasca-COVID.

**Interval prediksi: conformal prediction**
- Residual out-of-sample dari backtest dikumpulkan per horizon.
- Kuantil residual (80% dan 95%) menjadi lebar interval.
- Untuk LightGBM kuantil dipakai varian CQR (Conformalized Quantile Regression).
- Interval ini dibandingkan dengan interval bawaan SARIMAX dan interval kuantil mentah.

**Lapisan keputusan**

Kapasitas bulanan resmi belum tersedia, sehingga `ambang_kapasitas` dijadikan **parameter**
di `src/config.py`.

| Status | Kondisi (batas atas interval 95%) |
|---|---|
| Aman | di bawah 90% ambang |
| Waspada | antara 90% dan 100% ambang |
| Kritis | sama dengan atau di atas ambang |

Dilengkapi analisis sensitivitas (ambang digeser ±5% dan ±10%).

## 7. Evaluasi

**Rolling-origin backtest** (expanding window, tanpa pengacakan data): model dilatih pada
data sampai titik waktu tertentu, meramal 1–6 bulan ke depan, lalu jendela latih digeser maju.

| Metrik | Mengukur | Arah |
|---|---|---|
| MASE | Akurasi titik relatif terhadap seasonal naive | Makin kecil makin baik (di bawah 1 berarti lebih baik dari naive) |
| PICP | Persentase nilai aktual yang masuk interval | Mendekati level nominal (80% atau 95%) |
| MPIW | Rata-rata lebar interval | Makin kecil makin baik, asal PICP terpenuhi |
| Winkler score | Lebar interval ditambah penalti jika aktual di luar interval | Makin kecil makin baik |

RMSE dan MAE dipakai sebagai pendamping. MAPE tidak dijadikan metrik utama karena tidak
stabil pada nilai kecil (April–Mei 2020).

## 8. Struktur Repositori

```
prediksi-penumpang-krl-jabodetabek/
├── data/
│   ├── raw/                          # Data mentah BPS dan kalender (jangan diedit)
│   ├── processed/                    # Hasil pembersihan dan penggabungan
│   └── README.md                     # Dokumentasi data
├── notebooks/
│   ├── 01_data_prep.ipynb            # Gabung dan validasi data
│   ├── 02_eda.ipynb                  # Exploratory Data Analysis
│   ├── 03_features.ipynb             # Rekayasa fitur
│   ├── 04_baseline_sarimax.ipynb     # Baseline dan SARIMAX
│   ├── 05_lightgbm_conformal.ipynb   # LightGBM dan conformal prediction
│   └── 06_evaluasi_risiko.ipynb      # Evaluasi, risiko kapasitas, skenario
├── src/
│   ├── config.py                     # Parameter (ambang kapasitas, level interval, horizon)
│   ├── data_prep.py                  # Load dan pembersihan data
│   ├── features.py                   # Fitur waktu, lag, rolling window
│   ├── models.py                     # Baseline, SARIMAX, LightGBM, conformal
│   ├── backtest.py                   # Rolling-origin backtest
│   ├── metrics.py                    # MASE, PICP, MPIW, Winkler, RMSE, MAE
│   └── risk.py                       # Status risiko dan skenario kapasitas
├── outputs/                          # Hasil backtest (CSV) dan prediksi
├── reports/figures/                  # Grafik dan visualisasi laporan
├── app/                              # Dashboard Streamlit
├── requirements.txt
├── .gitignore
└── README.md
```

## 9. Cara Menjalankan

**1. Siapkan lingkungan**

```bash
git clone <url-repo>
cd prediksi-penumpang-krl-jabodetabek

python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux / macOS

pip install -r requirements.txt
```

Library utama: `pandas`, `numpy`, `matplotlib`, `scipy`, `statsmodels`, `lightgbm`,
`scikit-learn`, `holidays`, `streamlit`, `jupyter`.

**2. Letakkan data mentah**

Salin 11 file BPS (`Jumlah_Penumpang_Kereta_Api__<tahun>.csv`) dan
`kalender_eksogen_krl_2013_2026.csv` ke `data/raw/`.

**3. Jalankan notebook berurutan**

```
01_data_prep → 02_eda → 03_features → 04_baseline_sarimax → 05_lightgbm_conformal → 06_evaluasi_risiko
```

Notebook `01` harus dijalankan lebih dulu karena menghasilkan `data/processed/data_final.csv`
yang dipakai semua notebook berikutnya.

**4. Jalankan dashboard** (setelah tahap selesai)

```bash
streamlit run app/app.py
```

## 10. Status Pengerjaan

| Tahap | Status | Output Utama |
|---|---|---|
| Struktur folder dan dokumentasi data | Selesai | Kamus data, catatan kualitas BPS di `data/README.md` |
| 1. Persiapan data (`01_data_prep`) | Selesai | `data/processed/data_final.csv`, `kalender_future.csv` |
| 2. EDA (`02_eda`) | Selesai | Grafik musiman STL, uji ADF/KPSS, analisis tren pasca-COVID |
| 3. Rekayasa fitur (`03_features`) | Selesai | `fitur_lgbm_h1.csv` s/d `h6.csv`, regressor `data_sarimax.csv` |
| 4. Backtest dan baseline | Selesai | Rolling-origin backtest, skor benchmark ETS & Seasonal Naive |
| 5. SARIMAX dan LightGBM | Selesai | `src/models.py`, `04_baseline_sarimax.ipynb`, `05_lightgbm_conformal.ipynb` |
| 6. Conformal prediction | Selesai | Kalibrasi CQR interval 80% dan 95% (`outputs/metrik_interval_conformal.csv`) |
| 7. Evaluasi komparatif | Selesai | `outputs/metrik_komparasi_final.csv` (MASE, PICP, MPIW, Winkler) |
| 8. Lapisan keputusan | Selesai | `src/risk.py`, `06_evaluasi_risiko.ipynb`, analisis sensitivitas kapasitas |
| 9. Dashboard interaktif | Selesai | Aplikasi Streamlit di `app/app.py` |

### Ringkasan Hasil Empiris

- **Rentang data aktual**: Januari 2016 sampai Agustus 2026 (128 observasi bulanan).
- **Validasi total tahunan**: Cocok (konsisten 100% terhadap tabel BPS).
- **Kekuatan musiman (STL)**: Sangat kuat dengan penurunan signifikan di bulan Idul Fitri (rata-rata **-7.2%** dibanding bulan tetangga).
- **Hipotesis tren pasca-COVID**: Slope linear **+0.188 juta penumpang/bulan** (~8.2% per tahun, p < 0.001). Data membuktikan bahwa permintaan tetap bertumbuh namun mulai tertahan oleh batas atas kapasitas pada jam sibuk.
- **Kemenangan Model Cerdas vs Baseline (Periode Bersih)**:
  - **SARIMAX (0,1,1)(0,1,1)12**: **MASE = 0.524** | MAE = 1.022 ribu orang (~33% lebih akurat dari ETS).
  - **LightGBM Multi-Horizon**: **MASE = 0.600** | MAE = 1.170 ribu orang (terbaik di horizon h=2 dan h=3).
  - **Baseline Pembanding**: ETS (MASE = 0.783), Naive (0.794), Seasonal Naive (1.086).
- **Kualitas Interval Prediksi (Conformal Prediction)**:
  - Interval 80% menghasilkan cakupan empiris (**PICP**) sebesar **82.4% – 85.7%**.
  - Interval 95% menjamin cakupan 100% pada periode evaluasi, andal untuk dasar peringatan risiko kapasitas.

## 11. Keterbatasan

- **Sampel kecil** (sekitar 100–130 titik bulanan), sehingga dipilih model sederhana
  (SARIMAX dan gradient boosting kecil), bukan deep learning.
- **Patahan COVID** (2020–2022) memengaruhi estimasi parameter dan evaluasi.
- **Data tertahan kapasitas:** penumpang tercatat belum tentu sama dengan permintaan sebenarnya.
- **Ambang kapasitas bersifat asumsi,** karena kapasitas bulanan resmi belum ditemukan.
  Hasil status risiko harus dibaca bersama analisis sensitivitas.
- **Jaminan conformal bersifat aproksimasi,** karena data time series tidak saling bebas.
  Cakupan diukur secara empiris di data uji yang terpisah dari data kalibrasi.
- **Perbedaan sumber:** angka BPS dan KAI untuk tahun yang sama tidak identik.
- **Regressor masa depan:** `is_lebaran` dan hari kerja dapat diketahui sebelumnya, tetapi
  asumsi tidak ada gangguan besar baru (seperti COVID) tidak dapat dijamin.

## 12. Referensi

1. BPS. *Jumlah Penumpang Kereta Api.* https://www.bps.go.id/id/statistics-table/2/NzIjMg==/jumlah-penumpang-kereta-api.html
2. BPS. *Penumpang Angkutan Kereta Api Nasional Bulanan.* https://www.bps.go.id/en/statistics-table/2/MjM1MyMy/penumpang-angkutan-kereta-api-nasional-bulanan-.html
3. BPS Provinsi DKI Jakarta. *Jumlah Penumpang Kereta Api Menurut Bulan.* https://jakarta.bps.go.id/id/statistics-table/2/MTMyOSMy/jumlah-penumpang-kereta-api-menurut-bulan-orang-.html
4. DJKA Kemenhub. *Data Statistik (Penumpang PSO KRL Jabodetabek).* https://djka.dephub.go.id/statistik
5. Portal Satu Data Indonesia. *Jumlah Penumpang Kereta Api.* https://data.go.id/dataset/dataset/jumlah-penumpang-kereta-api
6. Repository ITS. *Peramalan Jumlah Penumpang KRL Commuter Line (DNN).* https://repository.its.ac.id/64545/
7. Kompas. *178 Juta Perjalanan KRL Jabodetabek pada Semester I 2026.* https://money.kompas.com/read/2026/08/04/164300926/178-juta-perjalanan-krl-jabodetabek-pada-semester-i-2026-kai--penambahan
8. RRI. *Commuter Line Melayani 178 Juta Perjalanan Selama Semester I 2026.* https://rri.co.id/ekonomi/bisnis/2619503/commuter-line-melayani-178-juta-perjalanan-selama-semester-i-2026
9. Kontan. *KRL Jabodetabek Overkapasitas hingga 161%.* https://industri.kontan.co.id/news/krl-jabodetabek-overkapasitas-hingga-161-kai-siapkan-penambahan-infrastruktur
10. Tirto. *KRL Jabodetabek Makin Sesak, Segerbong Bisa Capai 480 Penumpang.* https://tirto.id/krl-jabodetabek-makin-sesak-segerbong-bisa-capai-480-penumpang-hDde
11. Detik. *1 Juta Orang Desak-desakan di KRL Tiap Hari Kerja.* https://finance.detik.com/berita-ekonomi-bisnis/d-8601318/1-juta-orang-desak-desakan-di-krl-tiap-hari-kerja
12. CNN Indonesia. *Kemenhub Buat Kajian Tarif KRL Naik Rp1.000–Rp2.000 (2024).* https://www.cnnindonesia.com/ekonomi/20240912130431-92-1143769/kemenhub-buat-kajian-tarif-krl-naik-rp1000-rp2000
13. Eprints UNDIP. *Latar belakang studi pengguna KRL.* https://eprints2.undip.ac.id/42634/2/FARRA%20FRIZKA%20_14020122140135%20_BAB%20I.pdf

---

## Penulis

`[isi nama]` · `[isi NRP]` · Sains Data Terapan, PENS