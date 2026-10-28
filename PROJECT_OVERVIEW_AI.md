# DOKUMENTASI TEKNIS & PROMPT LENGKAP PROYEK SISTEM CERDAS
## Prediksi Permintaan Penumpang KRL Jabodetabek Berbasis Time Series dengan Interval Prediksi (Uncertainty Quantification) dan Lapisan Keputusan Risiko Kapasitas

---

## 1. Identitas Proyek & Konteks Akademik
- **Mata Kuliah:** Proyek Sistem Cerdas (Semester 5)
- **Program Studi:** Sains Data Terapan
- **Institusi:** Politeknik Elektronika Negeri Surabaya (PENS)
- **Repositori:** `LeandroJovan/prediksi-penumpang-krl-jabodetabek`
- **Fokus Utama:** Kombinasi antara *Point Forecasting*, *Uncertainty Quantification (Conformal Prediction)*, dan *Decision Intelligence (Sistem Peringatan Dini Kapasitas)*.

---

## 2. Latar Belakang Masalah & Urgensi Bisnis/Operasional
1. **Peran Kritis KRL Jabodetabek:**
   - KRL Commuter Line adalah urat nadi transportasi massal di wilayah aglomerasi Jabodetabek, melayani jutaan pekerja dan pelajar setiap hari kerja.
   - Volume perjalanan tahunan melonjak dari 168 juta (2021) menjadi sekitar 349 juta (2025). Pada semester I 2026, volume rata-rata melampaui 1,05 juta penumpang per hari kerja.
   - Jam sibuk (*peak hours*) pagi dan sore mengalami okupansi ekstrem berkisar antara 128% hingga 161% di koridor padat (seperti Bogor–Manggarai).

2. **Dilema Perencanaan & Kelemahan "Point Forecast":**
   - Penambahan armada, penambahan formasi rangkaian (SF10 ke SF12), perbaikan headway, dan upgrade gardu listrik membutuhkan investasi bernilai miliaran rupiah dan waktu pengadaan yang lama.
   - Model peramalan konvensional yang hanya mengeluarkan **satu angka tunggal (point forecast)** berbahaya bagi pengambil kebijakan: jika realisasi berada di atas estimasi titik, terjadi penumpukan penumpang ekstrem dan bahaya keselamatan; jika realisasi di bawahnya, terjadi pemborosan energi dan biaya operasional.
   - Oleh karena itu, proyek ini berfokus pada penyediaan **Prediction Interval (tingkat kepercayaan 80% dan 95%)** yang terkalibrasi secara empiris.

3. **Uji Hipotesis "Mendatar" (Capacity Censoring vs. Demand Saturation):**
   - Data BPS periode 2023–2026 menunjukkan volume penumpang bulanan berkisar di angka 27,8 – 30,6 juta orang per bulan. Angka ini mirip dengan tingkat penumpang pada Juli 2018 (sekitar 29,1 juta).
   - Muncul hipotesis: Apakah masyarakat mulai beralih moda transportasi (kejenuhan permintaan), ataukah angka penumpang yang tercatat **tersensor oleh batas fisik kapasitas KRL (*capacity bottleneck*)**? Proyek ini menguji fenomena tersebut secara empiris melalui analisis tren dan residual model.

---

## 3. Karakteristik Data & Kamus Data

### 3.1. Variabel Target
- **Sumber Data:** Badan Pusat Statistik (BPS) Republik Indonesia (sumber primer: PT Kereta Api Indonesia (Persero) / KAI Commuter).
- **Format Mentah:** 11 file CSV terpisah tahun 2016–2026 (`Jumlah Penumpang Kereta Api, <tahun>.csv`), berbentuk format *wide* per bulan (Jan–Des).
- **Kategori yang Digunakan:** Baris spesifik **`Jabodetabek`** (mengabaikan Non-Jabodetabek, Jawa non-Jabodetabek, dan Sumatera).
- **Granularitas Waktu:** Bulanan (*monthly* agregat seluruh jaringan Jabodetabek).
- **Satuan:** Ribu orang (`penumpang_ribu`).
- **Target Alternatif:** `penumpang_per_hari` (dihitung dengan membagi jumlah penumpang bulanan dengan jumlah hari kalender bulan tersebut guna menghilangkan variasi durasi 28/29/30/31 hari).

### 3.2. Variabel Eksogen (Kalender & Peristiwa)
Data kalender dibangkitkan dari library `holidays` Indonesia dan dicocokkan dengan kalender libur resmi pemerintah (`kalender_eksogen_krl_2013_2026.csv`):
- `jumlah_hari_kerja`: Total hari Senin–Jumat yang bukan hari libur nasional pada bulan tersebut.
- `selisih_hari_kerja_vs_tahun_lalu`: Perubahan jumlah hari kerja dibanding bulan yang sama tahun sebelumnya.
- `is_lebaran`: Indikator (1/0) apakah puncak perayaan Idul Fitri jatuh pada bulan tersebut. Lebaran menyebabkan penurunan drastis komuter harian karena libur panjang dan mudik.
- `lebaran_lag1`: Indikator efek pasca-Lebaran (arus balik komuter).
- `lebaran_lead1`: Indikator efek pra-Lebaran.
- `is_covid`: Indikator *structural break* (bernilai 1 untuk Maret 2020 hingga Desember 2022; 0 untuk periode lainnya).

---

## 4. Alur Kerja (End-to-End Pipeline)

Proyek ini dibangun secara modular mengikuti arsitektur 9 tahapan:

```
┌───────────────────────────────────────────────────────────────────────────┐
│ 1. Data Prep  ──>  2. EDA  ──>  3. Feature Engineering  ──>  4. Backtest  │
│                                                                           │
│ 5. Model Utama (SARIMAX & LightGBM)  ──>  6. Conformal Prediction         │
│                                                                           │
│ 7. Evaluasi Komparatif  ──>  8. Lapisan Keputusan  ──>  9. Streamlit App  │
└───────────────────────────────────────────────────────────────────────────┘
```

### Rincian Setiap Modul:
1. **Tahap 1: Persiapan Data (`notebooks/01_data_prep.ipynb`, `src/data_prep.py`)**
   - Mentransformasikan 11 tabel BPS dari format *wide* ke format *long*.
   - Melakukan *checksum validation*: Menjumlahkan 12 bulan dan membandingkannya dengan kolom `Tahunan` resmi BPS (`validasi_tahunan.csv`).
   - Menggabungkan seri target dengan tabel kalender menjadi dataset terintegrasi (`data/processed/data_final.csv`).

2. **Tahap 2: Exploratory Data Analysis (`notebooks/02_eda.ipynb`)**
   - Dekomposisi STL (*Seasonal-Trend decomposition using LOESS*) untuk mengekstrak kekuatan tren dan musiman (periode 12 bulan).
   - Pengujian stasioneritas formal: Augmented Dickey-Fuller (ADF) dan KPSS test.
   - Analisis Autokorelasi (ACF) dan Partial Autokorelasi (PACF).
   - Analisis korelasi antara jumlah hari kerja dengan volume penumpang.
   - Uji kemiringan (*slope*) tren pasca-2023 untuk memvalidasi hipotesis kurva mendatar.

3. **Tahap 3: Rekayasa Fitur (`notebooks/03_features.ipynb`, `src/features.py`)**
   - **Prinsip Utama:** Mengharamkan kebocoran data (*zero data leakage*).
   - Fitur masa lalu (hanya boleh mengakses data $\le$ titik origin $o$):
     - Lag target: `y_lag0` (nilai di origin), `y_lag1`, `y_lag2`.
     - Siklus tahunan: `y_tahun_lalu` (nilai bulan yang sama tahun lalu, $t - 12$).
     - Statistik bergerak: `roll_mean_3`, `roll_mean_12`.
   - Fitur kalender bulan target ($t = o + h$):
     - `bulan`, `bulan_sin`, `bulan_cos` (encoding siklus musiman).
     - `jumlah_hari_kerja`, `selisih_hari_kerja_vs_tahun_lalu`.
     - `is_lebaran`, `lebaran_lag1`, `lebaran_lead1`, `is_covid`.
   - Output: Tabel multi-horizon (`fitur_lgbm_h1.csv` sampai `fitur_lgbm_h6.csv`) serta fitur masa depan (`fitur_future_h*.csv`).

4. **Tahap 4: Backtesting & Baseline Model (`src/backtest.py`, `src/models.py`)**
   - Menerapkan **Expanding Window Rolling-Origin Backtest** (bukan *k-fold cross-validation* acak).
   - Origin awal ditetapkan pada Desember 2019 (48 bulan data latih awal: Jan 2016 – Des 2019).
   - Horizon peramalan $h = 1, 2, 3, 4, 5, 6$ bulan ke depan.
   - **Model Baseline:**
     - *Naive:* Nilai bulan terakhir dipertahankan.
     - *Seasonal Naive:* Nilai bulan yang sama tahun lalu ($t - 12$).
     - *ETS (Exponential Smoothing / Holt-Winters):* Tren aditif damped + komponen musiman aditif 12 bulan.
     - Variasi *Per-Hari Kalender:* Meramal rata-rata harian terlebih dahulu, lalu dikalikan jumlah hari kalender target.

5. **Tahap 5: Model Utama (`notebooks/04_baseline_sarimax.ipynb`, `notebooks/05_lightgbm_conformal.ipynb`)**
   - **SARIMAX:** Model deret waktu klasik dengan regressor eksogen (`jumlah_hari_kerja`, `is_lebaran`, `is_covid`).
   - **LightGBM:** Model *Gradient Boosted Decision Trees* tabular menggunakan pendekatan peramalan langsung (*Direct Multi-Horizon Forecasting*, membuat 1 model spesifik per horizon $h$). Dilatih untuk regresi titik (objektif L2/L1) dan regresi kuantil (*Quantile Regression* pada kuantil 0.025, 0.10, 0.50, 0.90, 0.975).

6. **Tahap 6: Interval Prediksi & Conformal Prediction (`notebooks/05_lightgbm_conformal.ipynb`)**
   - Mengatasi asumsi distribusi residual Gaussian/normal yang kerap meleset pada seri riil.
   - Menghitung residual *out-of-sample* historis dari proses backtest.
   - Menerapkan **Conformalized Quantile Regression (CQR)** dan Residual Quantile Calibration untuk menghasilkan interval 80% dan 95% yang memiliki jaminan cakupan empiris (*finite-sample coverage*).

7. **Tahap 7: Evaluasi Model (`src/metrics.py`, `notebooks/06_evaluasi_risiko.ipynb`)**
   - Model dievaluasi menggunakan metrik point forecast dan interval.
   - Model utama dinyatakan sah "Cerdas" hanya bila mengalahkan baseline Seasonal Naive dalam backtest.
   - Evaluasi dilaporkan dua kali: **All Periods** (termasuk pandemi) dan **Post-COVID Only** (data aktual $\ge$ Januari 2023).

8. **Tahap 8: Lapisan Keputusan Risiko Kapasitas (`src/risk.py`)**
   - Mengambil **Batas Atas Prediksi 95% (*Upper Bound 95%*)**.
   - Membandingkannya dengan `AMBANG_KAPASITAS` (dikonfigurasi pada `src/config.py`):
     - **Status Aman:** Batas atas < 90% ambang kapasitas.
     - **Status Waspada:** Batas atas antara 90% – 100% ambang kapasitas.
     - **Status Kritis:** Batas atas $\ge$ 100% ambang kapasitas (risiko tinggi penumpukan penumpang dan kegagalan layanan).
   - Menjalankan analisis sensitivitas dengan menguji ketahanan keputusan bila ambang digeser $\pm 5\%$ dan $\pm 10\%$.

9. **Tahap 9: Dashboard Interaktif (`app/app.py`)**
   - Antarmuka berbasis Streamlit bagi pemangku kepentingan (KAI Commuter / DJKA Kemenhub) untuk melihat proyeksi 6 bulan ke depan, batas interval ketidakpastian, dan rekomendasi status kapasitas.

---

## 5. Metrik Evaluasi Ilmiah

### A. Metrik Akurasi Titik (Point Forecast):
1. **MASE (Mean Absolute Scaled Error):**
   $$\text{MASE} = \frac{\text{MAE}}{\frac{1}{N-12}\sum_{t=13}^N |y_t - y_{t-12}|}$$
   - Metrik utama proyek. Nilai skala musiman dihitung hanya pada periode non-COVID agar pembagi tidak terdistorsi.
   - $\text{MASE} < 1.0$ membuktikan model lebih baik daripada Seasonal Naive.
2. **RMSE (Root Mean Squared Error):** Mengukur deviasi dengan bobot penalti lebih besar pada error ekstrem.
3. **MAE (Mean Absolute Error):** Rata-rata selisih absolut dalam ribuan penumpang.
4. *(Catatan Metrik MAPE):* MAPE hanya menjadi metrik pendamping, karena nilainya tidak stabil pada April–Mei 2020 saat penumpang anjlok akibat PSBB ketat.

### B. Metrik Akurasi Interval (Uncertainty Forecast):
1. **PICP (Prediction Interval Coverage Probability):**
   - Persentase titik observasi aktual yang jatuh di dalam rentang $[\hat{y}_{\text{lower}}, \hat{y}_{\text{upper}}]$.
   - Target nominal: $\ge 80\%$ untuk interval 80%, dan $\ge 95\%$ untuk interval 95%.
2. **MPIW (Mean Prediction Interval Width):**
   - Rata-rata lebar pita prediksi $(\hat{y}_{\text{upper}} - \hat{y}_{\text{lower}})$. Interval yang ideal adalah yang memiliki MPIW sekecil mungkin tanpa mengorbankan target PICP.
3. **Winkler Score:**
   - Metrik komprehensif yang mengukur lebar interval ditambah penalti proporsional jika nilai aktual meleset di luar batas interval.

---

## 6. Struktur Direktori Repositori

```
prediksi-penumpang-krl-jabodetabek/
├── data/
│   ├── raw/                             # File CSV asli BPS (2016-2026) dan kalender
│   ├── processed/                       # CSV hasil transformasi, fitur LGBM, data final
│   └── README.md                        # Dokumentasi kamus data & catatan kualitas
├── notebooks/
│   ├── 01_data_prep.ipynb               # ETL & checksum data BPS
│   ├── 02_eda.ipynb                     # Eksplorasi statistika time series
│   ├── 03_features.ipynb                # Pembentukan fitur lag & kalender
│   ├── 04_baseline_sarimax.ipynb        # Implementasi Naive, ETS, dan SARIMAX
│   ├── 05_lightgbm_conformal.ipynb      # LightGBM Quantile & Conformal Calibration
│   ├── 06_evaluasi_risiko.ipynb         # Komparasi metrik & simulasi risiko kapasitas
│   └── generate-data.ipynb              # Generator data kalender
├── src/
│   ├── config.py                        # Konfigurasi parameter global & ambang batas
│   ├── data_prep.py                     # Script parsing & integrasi data
│   ├── features.py                      # Fungsi pembentukan fitur no-leakage
│   ├── models.py                        # Arsitektur model peramalan
│   ├── backtest.py                      # Skema rolling-origin backtest
│   ├── metrics.py                       # Implementasi MASE, PICP, MPIW, Winkler
│   └── risk.py                          # Rule engine klasifikasi risiko kapasitas
├── outputs/                             # Hasil ekspor backtest & metrik evaluasi
├── reports/figures/                     # Grafik visualisasi resmi (EDA & Backtest)
├── app/                                 # Dashboard Streamlit
├── requirements.txt                     # Dependensi Python
├── README.md                            # Dokumentasi resmi proyek
└── PROJECT_OVERVIEW_AI.md               # Ringkasan konteks teknis untuk agen AI
```

---

## 7. Guardrails & Panduan Khusus untuk AI yang Melanjutkan Proyek

Jika Anda adalah agen AI yang membaca dokumen ini untuk melanjutkan atau mereview kode proyek ini:
1. **Jaga Prinsip Strict No-Leakage:**
   - Saat membuat fitur atau memodifikasi `src/features.py`, jangan pernah menggunakan operasi *rolling mean*, *lag*, atau target encoding yang mengintip baris setelah titik origin ($o$).
2. **Tangani Ukuran Data Kecil (Small N):**
   - Karena data bulanan hanya berjumlah ~120-130 baris, **jangan pernah menyarankan arsitektur Deep Learning (LSTM, GRU, Transformer, TFT)**. Model tersebut akan rentan *overfitting*. Utamakan model parsimonious: ETS, SARIMAX, dan LightGBM dengan kedalaman dangkal (*max_depth* kecil).
3. **Pembedaan Periode Evaluasi:**
   - Saat menghitung metrik performa di `src/metrics.py` atau `notebooks/`, pastikan selalu menampilkan metrik terpisah untuk:
     1. Seluruh periode backtest (2020–2026).
     2. Periode pasca-COVID (2023–2026) karena merupakan representasi dinamika normal operasional KRL saat ini.
4. **Interval Prediksi Harus Dikoneksikan ke Logika Bisnis:**
   - Prediksi batas atas (upper bound 95%) bukan sekadar angka statistik, melainkan variabel penentu status **Aman / Waspada / Kritis** di `src/risk.py`. Pastikan integrasi ini tetap konsisten hingga ke visualisasi dashboard.
