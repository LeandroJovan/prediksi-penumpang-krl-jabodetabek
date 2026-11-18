# Dokumentasi Folder `data/processed/`

Dokumen ini berisi penjelasan lengkap mengenai fungsi dari setiap berkas (file) di dalam folder [`data/processed/`](file:///c:/KULIAH/SEM%205/Project%20Sistem%20Cerdas/Prediksi%20KRL/prediksi-penumpang-krl-jabodetabek/data/processed) serta ringkasan alur dan tata cara penggunaan datanya dalam siklus pemodelan prediksi penumpang KRL Jabodetabek.

---

## 1. Ikhtisar & Taksonomi Berkas

Folder `processed/` menyimpan seluruh data turunan (*derived datasets*) yang telah dibersihkan, divalidasi, dan ditransformasikan menjadi bentuk siap latih (*model-ready*). Tidak ada data di folder ini yang diedit manual; seluruh berkas dibangkitkan secara otomatis melalui notebook persiapan data ([`01_data_prep.ipynb`](file:///c:/KULIAH/SEM%205/Project%20Sistem%20Cerdas/Prediksi%20KRL/prediksi-penumpang-krl-jabodetabek/notebooks/01_data_prep.ipynb)) dan rekayasa fitur ([`03_features.ipynb`](file:///c:/KULIAH/SEM%205/Project%20Sistem%20Cerdas/Prediksi%20KRL/prediksi-penumpang-krl-jabodetabek/notebooks/03_features.ipynb) / [`src/features.py`](file:///c:/KULIAH/SEM%205/Project%20Sistem%20Cerdas/Prediksi%20KRL/prediksi-penumpang-krl-jabodetabek/src/features.py)).

Secara umum, ke-18 berkas dalam folder ini dibagi menjadi 4 kelompok utama:

| Kelompok | Berkas | Fungsi Utama |
|---|---|---|
| **A. Data Hasil Agregasi & Audit Awal** | `data_final.csv`<br>`kalender_future.csv`<br>`validasi_tahunan.csv` | Menyatukan data historis BPS dan kalender dasar, mengaudit validitas angka tahunan, serta menyimpan kalender bulan depan. |
| **B. Data Model Time Series & Kalender Eksogen** | `data_sarimax.csv`<br>`kalender_fitur.csv` | Dataset deret waktu dengan variabel regressor eksogen untuk pemodelan SARIMAX dan acuan kalender lengkap. |
| **C. Dataset Pelatihan Machine Learning (LightGBM)** | `fitur_lgbm_h1.csv` s/d `fitur_lgbm_h6.csv` | Dataset fitur berorientasi *origin-target* untuk melatih 6 model LightGBM terpisah (*direct forecasting* $h=1$ hingga $h=6$). |
| **D. Dataset Fitur Prediksi Masa Depan (Inference)** | `fitur_future_h1.csv` s/d `fitur_future_h6.csv` | Baris fitur *unlabeled* masa depan yang siap diumpankan ke model untuk meramal 1–6 bulan ke depan dari titik data terakhir. |

---

## 2. Rincian & Fungsi Masing-Masing Berkas

### A. Data Agregasi & Audit Awal

#### 1. [`data_final.csv`](file:///c:/KULIAH/SEM%205/Project%20Sistem%20Cerdas/Prediksi%20KRL/prediksi-penumpang-krl-jabodetabek/data/processed/data_final.csv)
- **Asal Pembuatan**: [`notebooks/01_data_prep.ipynb`](file:///c:/KULIAH/SEM%205/Project%20Sistem%20Cerdas/Prediksi%20KRL/prediksi-penumpang-krl-jabodetabek/notebooks/01_data_prep.ipynb)
- **Fungsi**: Merupakan *single source of truth* data historis deret waktu bulanan. Menggabungkan data penumpang KRL Jabodetabek hasil pembersihan tabel BPS (2016–2026 berjalan) dengan fitur kalender dasar.
- **Rentang Data**: Januari 2016 s/d Agustus 2026 (128 bulan observasi aktual).
- **Struktur Kolom**:
  - `year_month`: Indeks periode dalam format teks `YYYY-MM`.
  - `tanggal`: Tanggal hari pertama tiap bulan (`YYYY-MM-01`).
  - `penumpang_ribu`: **Variabel Target Utama**. Total penumpang bulanan dalam satuan ribu orang.
  - `total_hari`: Total jumlah hari dalam bulan bersangkutan (28–31 hari).
  - `jumlah_hari_kerja`: Jumlah hari Senin–Jumat dikurangi libur nasional pada hari kerja.
  - `jumlah_libur_nasional_weekday`: Jumlah hari libur nasional yang jatuh pada hari kerja.
  - `is_lebaran`: Flag biner (1 jika bulan tersebut merupakan bulan Idul Fitri, 0 jika tidak).
  - `is_covid`: Flag biner (1 untuk periode pembatasan mobilitas pandemi Maret 2020 s/d Desember 2022).

#### 2. [`validasi_tahunan.csv`](file:///c:/KULIAH/SEM%205/Project%20Sistem%20Cerdas/Prediksi%20KRL/prediksi-penumpang-krl-jabodetabek/data/processed/validasi_tahunan.csv)
- **Asal Pembuatan**: [`notebooks/01_data_prep.ipynb`](file:///c:/KULIAH/SEM%205/Project%20Sistem%20Cerdas/Prediksi%20KRL/prediksi-penumpang-krl-jabodetabek/notebooks/01_data_prep.ipynb)
- **Fungsi**: Berkas audit jaminan mutu data (*Quality Assurance*). Menyimpan hasil perbandingan antara penjumlahan 12 bulan baris bulanan terhadap nilai agregat resmi pada kolom `Tahunan` dari data publikasi BPS.
- **Struktur Kolom**: `tahun`, `file`, `bulan_terisi`, `jumlah_12_bulan`, `tahunan_resmi`, `selisih`, `status`.
- **Interpretasi**: Tahun 2020–2025 menunjukkan status `OK` (selisih 0), sedangkan tahun 2016–2019 mencatat ketiadaan kolom tahunan pada format tabel mentah lama BPS.

#### 3. [`kalender_future.csv`](file:///c:/KULIAH/SEM%205/Project%20Sistem%20Cerdas/Prediksi%20KRL/prediksi-penumpang-krl-jabodetabek/data/processed/kalender_future.csv)
- **Asal Pembuatan**: [`notebooks/01_data_prep.ipynb`](file:///c:/KULIAH/SEM%205/Project%20Sistem%20Cerdas/Prediksi%20KRL/prediksi-penumpang-krl-jabodetabek/notebooks/01_data_prep.ipynb)
- **Fungsi**: Kalender eksogen untuk bulan-bulan masa depan yang data penumpangnya belum dirilis oleh BPS (September 2026 s/d Desember 2026).
- **Tujuan**: Menjamin ketersediaan informasi kalender (hari kerja, libur) saat sistem meramalkan masa depan.

---

### B. Data Model Time Series & Kalender Fitur

#### 4. [`data_sarimax.csv`](file:///c:/KULIAH/SEM%205/Project%20Sistem%20Cerdas/Prediksi%20KRL/prediksi-penumpang-krl-jabodetabek/data/processed/data_sarimax.csv)
- **Asal Pembuatan**: [`notebooks/03_features.ipynb`](file:///c:/KULIAH/SEM%205/Project%20Sistem%20Cerdas/Prediksi%20KRL/prediksi-penumpang-krl-jabodetabek/notebooks/03_features.ipynb)
- **Fungsi**: Dataset deret waktu yang siap diumpankan ke model ekonometrika / time series seperti SARIMAX (Seasonal AutoRegressive Integrated Moving Average with eXogenous regressors).
- **Rentang Data**: Januari 2016 s/d Desember 2026 (mencakup masa lalu dan masa depan untuk forecasting exog).
- **Struktur Kolom**:
  - `tanggal`: Indeks waktu bulanan.
  - `jumlah_hari_kerja`: Variabel eksogen jumlah hari kerja.
  - `is_lebaran`: Variabel eksogen bulan Lebaran.
  - `lebaran_lag1`: Variabel eksogen 1 bulan setelah Lebaran (arus balik/normalisasi).
  - `lebaran_lead1`: Variabel eksogen 1 bulan sebelum Lebaran (arus mudik/penurunan komuter).
  - `is_covid`: Variabel eksogen shock pandemi.
  - `penumpang_ribu`: Target utama bulanan.
  - `penumpang_per_hari_kerja`: Target alternatif berupa rasio rata-rata harian pada hari kerja (`penumpang_ribu / jumlah_hari_kerja`).

#### 5. [`kalender_fitur.csv`](file:///c:/KULIAH/SEM%205/Project%20Sistem%20Cerdas/Prediksi%20KRL/prediksi-penumpang-krl-jabodetabek/data/processed/kalender_fitur.csv)
- **Asal Pembuatan**: [`src/features.py`](file:///c:/KULIAH/SEM%205/Project%20Sistem%20Cerdas/Prediksi%20KRL/prediksi-penumpang-krl-jabodetabek/src/features.py) (`buat_fitur_kalender()`)
- **Fungsi**: Tabel referensi fitur kalender yang diperluas (*extended calendar features*) yang mencakup seluruh rentang historis dan proyeksi masa depan. Digunakan sebagai dasar pembentukan regressor eksogen untuk SARIMAX dan fitur kalender untuk LightGBM.
- **Struktur Kolom**: `tanggal`, `jumlah_hari_kerja`, `is_lebaran`, `lebaran_lag1`, `lebaran_lead1`, `is_covid`.

---

### C. Dataset Pelatihan LightGBM (`fitur_lgbm_h1.csv` s/d `fitur_lgbm_h6.csv`)

- **Asal Pembuatan**: [`notebooks/03_features.ipynb`](file:///c:/KULIAH/SEM%205/Project%20Sistem%20Cerdas/Prediksi%20KRL/prediksi-penumpang-krl-jabodetabek/notebooks/03_features.ipynb)
- **Metode**: Pendekatan *Direct Multi-Step Forecasting*. Alih-alih meramalkan secara rekursif (yang dapat mengakumulasi galat kesalahan), proyek ini melatih **6 model berbeda** untuk masing-masing horizon peramalan:
  - `fitur_lgbm_h1.csv`: Model untuk meramal 1 bulan ke depan ($t = o + 1$).
  - `fitur_lgbm_h2.csv`: Model untuk meramal 2 bulan ke depan ($t = o + 2$).
  - `fitur_lgbm_h3.csv`: Model untuk meramal 3 bulan ke depan ($t = o + 3$).
  - `fitur_lgbm_h4.csv`: Model untuk meramal 4 bulan ke depan ($t = o + 4$).
  - `fitur_lgbm_h5.csv`: Model untuk meramal 5 bulan ke depan ($t = o + 5$).
  - `fitur_lgbm_h6.csv`: Model untuk meramal 6 bulan ke depan ($t = o + 6$).
- **Prinsip Utama Bebas Kebocoran Data (*No Data Leakage*)**:
  Setiap baris berindeks titik asal (*origin* $o$). Fitur masa lalu hanya boleh mengambil informasi hingga bulan $o$. Informasi bulan $t$ yang boleh digunakan hanyalah fitur kalender deterministik yang secara alamiah sudah diketahui di muka.
- **Kamus Fitur (15 Kolom Fitur + 3 Kolom Info)**:

| Nama Kolom | Kategori | Penjelasan & Formulasi |
|---|---|---|
| `y_lag0` | Masa Lalu | Nilai penumpang di titik origin ($o$) |
| `y_lag1` | Masa Lalu | Nilai penumpang 1 bulan sebelum origin ($o - 1$) |
| `y_lag2` | Masa Lalu | Nilai penumpang 2 bulan sebelum origin ($o - 2$) |
| `y_tahun_lalu` | Masa Lalu | Nilai penumpang bulan yang sama tahun lalu dari bulan target ($t - 12 = o + h - 12$) |
| `roll_mean_3` | Masa Lalu | Rata-rata bergerak 3 bulan terakhir sampai origin |
| `roll_mean_12` | Masa Lalu | Rata-rata bergerak 12 bulan terakhir sampai origin |
| `bulan` | Kalender Target | Angka bulan target ($1$ sampai $12$) |
| `bulan_sin` | Kalender Target | Transformasi siklik sinus: $\sin(2\pi \cdot \text{bulan} / 12)$ |
| `bulan_cos` | Kalender Target | Transformasi siklik kosinus: $\cos(2\pi \cdot \text{bulan} / 12)$ |
| `jumlah_hari_kerja` | Kalender Target | Jumlah hari kerja di bulan target $t$ |
| `selisih_hari_kerja_vs_tahun_lalu` | Kalender Target | Selisih hari kerja bulan target vs bulan target tahun lalu |
| `is_lebaran` | Kalender Target | Indikator Idul Fitri di bulan target |
| `lebaran_lag1` | Kalender Target | Indikator bulan setelah Lebaran untuk bulan target |
| `lebaran_lead1` | Kalender Target | Indikator bulan sebelum Lebaran untuk bulan target |
| `is_covid` | Kalender Target | Indikator status pandemi di bulan target |
| `tanggal_target` | **Info/Target** | Tanggal target yang diramal ($t = o + h$) |
| `y_target` | **Info/Target** | **Nilai aktual target** pada bulan target (label supervisi training) |
| `tercemar_covid` | **Info/Evaluasi** | Bernilai 1 jika dalam 12 bulan sebelum origin atau tahun lalu terdapat bulan pandemi. Digunakan untuk memisahkan evaluasi kinerja pasca-COVID murni. |

---

### D. Dataset Fitur Prediksi Masa Depan (`fitur_future_h1.csv` s/d `fitur_future_h6.csv`)

- **Asal Pembuatan**: [`notebooks/03_features.ipynb`](file:///c:/KULIAH/SEM%205/Project%20Sistem%20Cerdas/Prediksi%20KRL/prediksi-penumpang-krl-jabodetabek/notebooks/03_features.ipynb)
- **Fungsi**: Berkas inferensi untuk memproyeksikan peramalan *out-of-sample*.
- **Karakteristik**:
  - Memiliki struktur kolom yang identik dengan `fitur_lgbm_h*.csv`.
  - Mengambil titik asal (*origin*) data riil terakhir (yaitu `2026-08-01`).
  - Kolom `y_target` bernilai kosong (NaN) karena data realisasi belum terjadi.
  - Untuk masing-masing $h \in \{1, \dots, 6\}$, berkas ini memetakan prediksi menuju September 2026 ($h=1$) hingga Februari 2027 ($h=6$).

---

## 3. Ringkasan Mengenai Penggunaan Datanya

Berikut adalah siklus pemanfaatan berkas-berkas di atas dalam arsitektur proyek peramalan KRL:

```
                      [Data Mentah BPS & Kalender]
                                   │
                                   ▼
                       [01_data_prep.ipynb]
                                   │
            ┌──────────────────────┴──────────────────────┐
            ▼                                             ▼
   [data_final.csv]                              [kalender_future.csv]
   [validasi_tahunan.csv]                                 │
            │                                             │
            └──────────────────────┬──────────────────────┘
                                   ▼
                         [03_features.ipynb]
                                   │
        ┌──────────────────────────┼──────────────────────────┐
        ▼                          ▼                          ▼
 [data_sarimax.csv]      [fitur_lgbm_h1..h6.csv]    [fitur_future_h1..h6.csv]
 [kalender_fitur.csv]              │                          │
        │                          │                          │
        ▼                          ▼                          │
 [Pemodelan SARIMAX]     [Pelatihan LightGBM]                 │
 (04_baseline_sarimax)   (Backtest & Conformal)               │
        │                          │                          │
        └──────────────┬───────────┘                          │
                       ▼                                      │
              [Evaluasi & Model Terbaik]                      ▼
                       │                             [Inferensi Masa Depan]
                       └─────────────────────────────► (Prediksi Point + Interval)
                                                              │
                                                              ▼
                                                   [Dashboard Keputusan KRL]
```

### 1. Tahap Audit & Pembersihan (Data Quality Assurance)
- `validasi_tahunan.csv` diperiksa terlebih dahulu untuk memastikan tidak ada kesalahan penjumlahan data bulanan BPS sebelum proses pemodelan dimulai.
- `data_final.csv` menjadi basis seluruh analisis eksplorasi data (EDA) pada [`02_eda.ipynb`](file:///c:/KULIAH/SEM%205/Project%20Sistem%20Cerdas/Prediksi%20KRL/prediksi-penumpang-krl-jabodetabek/notebooks/02_eda.ipynb), seperti dekomposisi musiman STL, analisis dampak Lebaran, dan pengujian stasioneritas (ADF & KPSS).

### 2. Tahap Pemodelan Baseline & Ekonometrika (SARIMAX)
- `data_sarimax.csv` dan `kalender_fitur.csv` digunakan pada [`04_baseline_sarimax.ipynb`](file:///c:/KULIAH/SEM%205/Project%20Sistem%20Cerdas/Prediksi%20KRL/prediksi-penumpang-krl-jabodetabek/notebooks/04_baseline_sarimax.ipynb).
- Model memanfaatkan target `penumpang_ribu` atau `penumpang_per_hari_kerja` bersama regressor kalender (`jumlah_hari_kerja`, `is_lebaran`, `lebaran_lag1`, `lebaran_lead1`, `is_covid`) untuk menangkap komponen tren, musiman, dan efek kalender secara simultan.

### 3. Tahap Pemodelan Machine Learning & Evaluasi Berulang (Backtesting)
- Berkas `fitur_lgbm_h1.csv` hingga `fitur_lgbm_h6.csv` digunakan dalam prosedur validasi silang deret waktu (*rolling-origin backtest*) di [`src/backtest.py`](file:///c:/KULIAH/SEM%205/Project%20Sistem%20Cerdas/Prediksi%20KRL/prediksi-penumpang-krl-jabodetabek/src/backtest.py).
- Kolom `tercemar_covid` dimanfaatkan saat evaluasi model untuk memfilter metrik performa (MASE, RMSE, MAPE) khusus pada rezim normal pasca-COVID (2023–2026), sehingga evaluasi tidak bias oleh anomali ekstrem saat pandemi.

### 4. Tahap Pembentukan Interval Prediksi (Conformal Prediction)
- Residual (selisih prediksi vs `y_target`) dari proses backtest pada berkas `fitur_lgbm_h*.csv` digunakan untuk mengkalibrasi batas ketidakpastian non-parametrik dengan metode **Conformal Prediction**.
- Menghasilkan interval prediksi tingkat keyakinan 80% dan 95% (batas bawah dan batas atas) yang memiliki jaminan cakupan teoretis terkalibrasi.

### 5. Tahap Operasional & Inferensi Masa Depan (Dashboard Interaktif)
- Model terpilih memuat berkas `fitur_future_h1.csv` s/d `fitur_future_h6.csv` untuk memprediksi volume penumpang KRL 6 bulan ke depan secara langsung.
- Batas atas prediksi ($Q_{upper}$) dibandingkan dengan ambang batas kapasitas armada KRL (misal: 38,3 juta penumpang/bulan) pada modul risiko ([`src/risk.py`](file:///c:/KULIAH/SEM%205/Project%20Sistem%20Cerdas/Prediksi%20KRL/prediksi-penumpang-krl-jabodetabek/src/risk.py)) dan ditampilkan di dashboard interaktif ([`app/`](file:///c:/KULIAH/SEM%205/Project%20Sistem%20Cerdas/Prediksi%20KRL/prediksi-penumpang-krl-jabodetabek/app)) dengan indikator status risiko:
  - **Aman (Hijau)**: Batas atas masih di bawah ambang kapasitas.
  - **Waspada (Kuning)**: Batas atas mendekati kapasitas (margin tipis).
  - **Bahaya / Overcapacity (Merah)**: Batas atas melampaui kapasitas armada, menandakan perlunya penambahan frekuensi perjalanan / stamformasi kereta.

---

## 4. Cara Mereproduksi Berkas di Folder Ini

Jika terdapat pembaruan data bulanan baru dari BPS:

1. Simpan berkas mentah BPS terbaru ke dalam folder [`data/raw/`](file:///c:/KULIAH/SEM%205/Project%20Sistem%20Cerdas/Prediksi%20KRL/prediksi-penumpang-krl-jabodetabek/data/raw).
2. Jalankan notebook [`notebooks/01_data_prep.ipynb`](file:///c:/KULIAH/SEM%205/Project%20Sistem%20Cerdas/Prediksi%20KRL/prediksi-penumpang-krl-jabodetabek/notebooks/01_data_prep.ipynb) untuk memperbarui `data_final.csv`, `kalender_future.csv`, dan `validasi_tahunan.csv`.
3. Jalankan notebook [`notebooks/03_features.ipynb`](file:///c:/KULIAH/SEM%205/Project%20Sistem%20Cerdas/Prediksi%20KRL/prediksi-penumpang-krl-jabodetabek/notebooks/03_features.ipynb) untuk meregenerasi seluruh berkas fitur `data_sarimax.csv`, `kalender_fitur.csv`, `fitur_lgbm_h*.csv`, dan `fitur_future_h*.csv`.
