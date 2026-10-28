# 🛠️ Petunjuk Teknis untuk Tim Back-End
## Proyek Sistem Cerdas: Prediksi Permintaan Penumpang KRL Jabodetabek

Dokumen ini disusun khusus sebagai panduan operasional bagi pengembang **Back-End** dalam mengelola model machine learning, arsitektur REST API, pemrosesan batch, dan skema data.

---

## 1. Tanggung Jawab Tim Back-End
1. Menyediakan layanan API (*serving layer*) agar Front-End dapat mengakses hasil peramalan secara asinkron atau real-time.
2. Mengelola pembaruan data bulanan (*data ingestion & retraining pipeline*).
3. Mengatur konfigurasi ambang batas operasional pada file konfigurasi sentral.

---

## 2. Struktur Direktori Terkait Back-End

```
prediksi-penumpang-krl-jabodetabek/
├── backend/
│   └── api.py                    # Server REST API (Flask)
├── src/                          # Modul inti Machine Learning
│   ├── config.py                 # Parameter sentral proyek
│   ├── features.py               # Rekayasa fitur (lag, rolling, kalender)
│   ├── models.py                 # Algoritma SARIMAX, LightGBM, Conformal (CQR)
│   ├── risk.py                   # Logika penentuan status risiko kapasitas
│   └── metrics.py                # Kalkulasi MASE, PICP, MPIW, Winkler
├── data/
│   ├── raw/                      # Data mentah bulanan BPS (2016-2026)
│   └── processed/                # Data final dan tabel fitur per horizon
└── outputs/                      # File artefak prediksi & evaluasi
    ├── prediksi_future_6bln.csv  # Output prakiraan 6 bulan + interval
    ├── metrik_komparasi_final.csv# Tabel performa model
    └── tabel_status_risiko_kapasitas.csv
```

---

## 3. Server REST API (`backend/api.py`)

File backend API siap pakai telah disediakan di [`backend/api.py`](file:///C:/Users/LENOVO/OneDrive/Documents/KULIAH%20COYYY/SEMESTER%205/Sistem%20Cerdas/prediksi-penumpang-krl-jabodetabek/backend/api.py).

### Cara Menjalankan API Server:
```bash
python backend/api.py
```
Server akan berjalan di: `http://localhost:5000`

---

## 4. Spesifikasi Endpoints API (API Contract)

### A. Health Check
- **Endpoint**: `GET /api/health`
- **Tujuan**: Memastikan server backend aktif.
- **Response `200 OK`**:
  ```json
  {
    "status": "healthy",
    "service": "KRL Ridership Forecasting & Risk Capacity API",
    "version": "1.0.0"
  }
  ```

### B. Ambil Prakiraan 6 Bulan
- **Endpoint**: `GET /api/forecast`
- **Query Params (Opsional)**:
  - `ambang_kapasitas`: float (default: `34000.0`)
  - `batas_waspada`: float (default: `0.90`)
- **Response `200 OK`**:
  ```json
  {
    "ambang_kapasitas_aktif": 34000.0,
    "batas_waspada_rasio": 0.9,
    "data": [
      {
        "horizon": 1,
        "tanggal_target": "2026-09-01",
        "y_pred_titik": 31304.6,
        "batas_bawah_80": 29643.8,
        "batas_atas_80": 32965.5,
        "batas_bawah_95": 29039.1,
        "batas_atas_95": 33570.1,
        "okupansi_batas_atas_%": 98.7,
        "status_risiko": "Waspada"
      },
      {
        "horizon": 2,
        "tanggal_target": "2026-10-01",
        "y_pred_titik": 31365.3,
        "batas_bawah_80": 29743.5,
        "batas_atas_80": 32987.1,
        "batas_bawah_95": 28347.4,
        "batas_atas_95": 34383.3,
        "okupansi_batas_atas_%": 101.1,
        "status_risiko": "Kritis"
      }
    ]
  }
  ```

### C. Simulasi Risiko Kapasitas Reaktif
- **Endpoint**: `POST /api/simulate-risk`
- **Tujuan**: Dipanggil saat pengguna di Front-End menggeser slider kapasitas atau mengubah tingkat interval.
- **Request Body (JSON)**:
  ```json
  {
    "ambang_kapasitas": 32000.0,
    "batas_waspada": 0.90,
    "kolom_batas_atas": "batas_atas_95"
  }
  ```
- **Response `200 OK`**:
  ```json
  {
    "ambang_kapasitas": 32000.0,
    "batas_waspada": 0.9,
    "status_global": "Kritis",
    "ringkasan": {
      "rata_rata_prediksi": 31139.5,
      "puncak_batas_atas": 35355.3,
      "okupansi_maksimum_%": 110.5
    },
    "detail": [...]
  }
  ```

### D. Ambil Metrik Performa Model
- **Endpoint**: `GET /api/metrics?subset=bersih`
- **Response `200 OK`**:
  ```json
  [
    {"model": "SARIMAX", "MAE": 1022.5, "RMSE": 1286.5, "MAPE_%": 3.59, "MASE": 0.524},
    {"model": "LightGBM", "MAE": 1170.8, "RMSE": 1521.4, "MAPE_%": 3.95, "MASE": 0.600},
    {"model": "ETS_tanpa_musim", "MAE": 1527.9, "RMSE": 1877.2, "MAPE_%": 5.25, "MASE": 0.783}
  ]
  ```

---

## 5. Prosedur Ingestion Data Baru (Monthly Ingestion)
Jika operator atau BPS menerbitkan data rilis bulan baru:
1. Masukkan baris baru ke `data/processed/data_final.csv` (kolom: `tanggal`, `penumpang_ribu`).
2. Jalankan notebook `03_features.ipynb` atau fungsi `buat_fitur_lightgbm()` di `src/features.py`.
3. Panggil fungsi inference `prediksi_lightgbm()` dan `ramal_sarimax_interval()` di `src/models.py`.
4. Perbarui file `outputs/prediksi_future_6bln.csv`.
