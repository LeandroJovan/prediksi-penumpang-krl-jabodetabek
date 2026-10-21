# Prediksi Penumpang KRL Jabodetabek

Proyek analisis deret waktu (*time series forecasting*) dan pemodelan prediktif untuk memproyeksikan jumlah penumpang KRL Commuter Line Jabodetabek dengan pendekatan kuantifikasi ketidakpastian (*uncertainty quantification* / conformal prediction) dan evaluasi risiko.

---

## 📁 Struktur Direktori

```text
prediksi-penumpang-krl-jabodetabek/
├── data/
│   ├── raw/                  # Data mentah asli dari BPS (jangan diedit)
│   ├── processed/            # Data hasil pembersihan dan rekayasa fitur
│   └── README.md             # Dokumentasi sumber, tanggal akses, dan satuan data
├── notebooks/
│   ├── 01_eda.ipynb          # Exploratory Data Analysis
│   ├── 02_preprocessing.ipynb# Data cleaning, outlier handling & feature engineering
│   ├── 03_baseline_sarimax.ipynb  # Pemodelan baseline statistik (SARIMAX)
│   ├── 04_lightgbm_conformal.ipynb# Pemodelan ML (LightGBM) & Conformal Prediction
│   └── 05_evaluasi_risiko.ipynb   # Analisis skenario, evaluasi risiko & metrik bisnis
├── src/
│   ├── data_prep.py          # Modul load & pembersihan data
│   ├── features.py           # Ekstraksi fitur waktu, lag, dan rolling window
│   ├── models.py             # Definisi pipeline model (SARIMAX, LightGBM, MAPIE)
│   ├── backtest.py           # Validasi deret waktu (Time-Series Split / Expanding Window)
│   ├── metrics.py            # Perhitungan metrik evaluasi (RMSE, MAE, MAPE, Coverage)
│   └── risk.py               # Analisis risiko, interval prediksi, dan skenario kapasitas
├── reports/
│   └── figures/              # Grafik, plot peramalan, dan visualisasi laporan
├── app/                      # Aplikasi interaktif dashboard (Streamlit)
├── requirements.txt          # Dependensi pustaka Python
├── .gitignore                # File filter git
└── README.md                 # Dokumentasi utama proyek
```

---

## 🛠️ Tech Stack & Dependensi

- **Bahasa:** Python 3.10+
- **Manipulasi Data:** `pandas`, `numpy`, `scipy`
- **Visualisasi:** `matplotlib`, `seaborn`, `plotly`
- **Pemodelan & Statistik:** `statsmodels`, `pmdarima`, `scikit-learn`, `lightgbm`
- **Uncertainty Quantification:** `mapie` (Conformal Prediction)
- **Deployment / UI (Opsional):** `streamlit`

---

## 🚀 Panduan Memulai

### 1. Inisialisasi Virtual Environment
```bash
python -m venv venv
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# Linux / macOS:
source venv/bin/activate
```

### 2. Instalasi Dependensi
```bash
pip install -r requirements.txt
```

---

## 📊 Alur Proyek (*Project Pipeline*)

1. **Eksplorasi Data (EDA):** Identifikasi tren musiman (*seasonality*), pola tahunan, anomali periode pandemi, serta stasioneritas data.
2. **Preprocessing & Feature Engineering:** Penanganan *missing values*, pembuatan fitur *lag*, *rolling mean/std*, serta indikator kalender (libur nasional/hari kerja).
3. **Pemodelan Baseline:** Model statistik klasik (SARIMAX) sebagai acuan performa dasar.
4. **Machine Learning & Conformal Prediction:** Pelatihan model LightGBM dengan estimasi interval kepercayaan menggunakan *Conformal Prediction* (MAPIE) untuk mengukur ketidakpastian proyeksi.
5. **Evaluasi Risiko:** Pengujian skenario lonjakan (*surge demand*) dan risiko *underestimation/overestimation* bagi operasional KRL.