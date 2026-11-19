# KRL Forecast Backend (FastAPI Engine)

FastAPI REST API untuk menyajikan hasil peramalan penumpang KRL Jabodetabek, evaluasi risiko kapasitas infrastruktur, metrik performa model, dan AI insight.

---

## 🚀 Fitur Utama

- **Serving Layer Multi-Horizon**: Prediksi 1–6 bulan ke depan dengan estimasi titik dan interval konformal (80% & 95%).
- **Simulasi Reaktif Risiko Kapasitas**: Kalkulasi dinamis berdasarkan slider kapasitas bulanan maupun pembagian harian (*weekday* vs *weekend*).
- **Dual Runtime Support**:
  - **Local Zero-Config**: Menggunakan SQLite (`sqlite+aiosqlite`) dan *in-memory cache* otomatis tanpa perlu instalasi Docker/Redis.
  - **Production/Docker**: Menggunakan PostgreSQL (`asyncpg`), Redis, dan Ollama LLM.
- **Auto-Seeding & Pipeline Fallback**: Database otomatis mengimpor data historis BPS dan artefak peramalan ML pada saat *startup*.
- **Integrated Static Frontend**: Otomatis me-mount folder `frontend/` di root URL (`http://localhost:8000/`).

---

## 💻 Menjalankan Server Lokal (Windows / Linux / macOS)

### Cara Cepat (Windows Batch Script):
Cukup klik ganda file:
```bash
jalankan_backend_fastapi.bat
```
Browser akan otomatis membuka dokumentasi interaktif Swagger di `http://localhost:8000/docs`.

### Cara Manual via Uvicorn:
```bash
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 🐳 Menjalankan via Docker Compose

1. Salin konfigurasi environment:
   ```bash
   cp backend/.env.example backend/.env
   ```
2. Jalankan container:
   ```bash
   docker compose up --build -d
   ```
3. Akses Swagger UI di `http://localhost:8000/docs`.

---

## 📡 Daftar Endpoint REST API (`/api/v1`)

| Method | Endpoint | Deskripsi |
|---|---|---|
| `GET` | `/api/v1/health` | Health check status server |
| `GET` | `/api/v1/meta` | Metadata periode data, model aktif, dan konfigurasi kapasitas |
| `GET` | `/api/v1/passengers` | Deret waktu penumpang bulanan historis (2016–2026) |
| `GET` | `/api/v1/forecasts/latest` | Prediksi 6 bulan + interval 80% & 95% + status risiko |
| `GET` | `/api/v1/risk/latest` | Status risiko kapasitas terkini |
| `POST` | `/api/v1/risk/simulate` | Simulasi reaktif perubahan kapasitas & tingkat interval |
| `GET` | `/api/v1/risk/sensitivity` | Tabel matriks analisis sensitivitas pergeseran kapasitas (-10% s.d. +10%) |
| `GET` | `/api/v1/metrics` | Skor performa model (MASE, MAE, RMSE, MAPE, PICP) |
| `GET` | `/api/v1/models` | Daftar model peramalan terdaftar dalam sistem |
| `GET` | `/api/v1/models/{run_id}` | Detail kartu model dan pustaka algoritma |
| `GET` | `/api/v1/insights/latest` | Narasi wawasan operasional AI berbasis fakta risiko |

---

## 🧪 Menjalankan Pengujian (Testing)

Jalankan pengujian otomatis menggunakan `pytest`:
```bash
python -m pytest backend/tests -v
```
Seluruh 15 pengujian unit dan integrasi mencakup health check, forecast, simulasi risiko, metrik, seeding, dan frontend mounting.
