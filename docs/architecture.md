# Arsitektur Backend KRL Forecast

Dokumen ini adalah acuan teknis untuk backend FastAPI pada proyek **Prediksi Permintaan
Penumpang KRL Jabodetabek**. Dokumen mencakup keputusan arsitektur, kontrak API, skema
database, strategi inference, caching, keamanan, deployment, dan roadmap.

Status: **draft arsitektur**, belum implementasi.

---

## 1. Tujuan dan Ruang Lingkup

Backend bertugas:

1. Menyajikan data historis penumpang KRL Jabodetabek.
2. Menyajikan forecast bulanan beserta interval prediksi 80% dan 95%.
3. Menghitung status risiko kapasitas dari batas atas interval.
4. Menyajikan metrik evaluasi dan model card.
5. Menyediakan simulasi ambang kapasitas tanpa mengubah data.
6. Menyajikan frontend statis HTML/CSS/JS.

Backend **tidak** bertugas:

- Melatih model.
- Melakukan upload data atau retrain melalui API pada MVP.
- Mengelola user/login.

Model dilatih di notebook, diekspor sebagai pickle bundle, lalu dimuat oleh backend.
Inference dijalankan **per request dengan cache**.

---

## 2. Keputusan Arsitektur

| Aspek | Keputusan | Alasan |
|---|---|---|
| Gaya arsitektur | Modular monolith | Skala proyek tidak membutuhkan microservices |
| Framework | FastAPI | Async, OpenAPI otomatis, validasi Pydantic |
| Database | PostgreSQL | Kebutuhan query, audit, dan JSONB |
| ORM/migrasi | SQLAlchemy 2.0 async + Alembic | Standar, mudah diuji, mendukung async |
| Driver | asyncpg | Performa async untuk PostgreSQL |
| Model | Pickle `ForecastBundle` | Notebook menjadi satu-satunya tempat training |
| Inference | Per request + cache | Fleksibel, tetap cepat untuk request berulang |
| Model lifecycle | Preload saat aplikasi siap | Tidak melakukan `joblib.load()` pada request pertama |
| Shared cache | Redis | Cache konsisten antar worker dan container |
| AI summary | Ollama lokal, grounded structured output | Risiko tetap deterministik dan data tidak keluar server |
| Frontend | HTML/CSS/JS statis | Sesuai kebutuhan, tanpa build tool |
| Serving frontend | FastAPI `StaticFiles` | Satu origin, tanpa CORS di produksi |
| Auth | Public read + `X-API-Key` admin | Cukup untuk proyek akademik |
| Kapasitas | Turunan kapasitas harian | Lebih realistis daripada satu angka bulanan |
| Deployment | Docker Compose | Reproducible, mudah dijalankan lokal |

---

## 3. Diagram Komponen

```text
┌──────────────────────────────────────────────────────────────┐
│ Browser                                                       │
│  HTML + CSS + JS + Chart.js                                   │
└──────────────────────────┬───────────────────────────────────┘
                           │ same-origin
                           ▼
┌──────────────────────────────────────────────────────────────┐
│ FastAPI                                                       │
│                                                               │
│  /                    StaticFiles(frontend/)                  │
│  /docs                Swagger UI                              │
│  /api/v1/*            REST API                                │
│                                                               │
│  Middleware                                                   │
│   ├── Request ID                                              │
│   ├── Structured logging                                      │
│   ├── CORS (dev)                                              │
│   ├── Rate limit                                              │
│   └── RFC 7807 error handler                                  │
│                                                               │
│  Routers                                                      │
│   ├── health                                                  │
│   ├── meta                                                    │
│   ├── passengers                                              │
│   ├── forecasts                                               │
│   ├── models                                                  │
│   ├── metrics                                                 │
│   └── risk                                                    │
│                                                               │
│  Services                                                     │
│   ├── HistoryService                                          │
│   ├── ForecastService                                         │
│   ├── RiskService                                             │
│   ├── MetricsService                                          │
│   └── ModelRegistry                                           │
└───────────────┬──────────────────────────────┬────────────────┘
                │                              │
                ▼                              ▼
       PostgreSQL                     artifacts/models/<run_id>/
       ├── actuals                    ├── model.pkl
       ├── calendar                   ├── manifest.json
       ├── data_versions              └── model_card.json
       ├── model_runs
       └── metrics
```

---

## 4. Struktur Folder

```text
KRL Forecast Sisdas/
├── backend/
│   ├── pyproject.toml
│   ├── requirements.lock
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── alembic.ini
│   ├── .env.example
│   ├── app/
│   │   ├── main.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── logging.py
│   │   │   ├── errors.py
│   │   │   ├── security.py
│   │   │   └── middleware.py
│   │   ├── api/
│   │   │   ├── deps.py
│   │   │   └── v1/
│   │   │       ├── router.py
│   │   │       └── endpoints/
│   │   │           ├── health.py
│   │   │           ├── meta.py
│   │   │           ├── passengers.py
│   │   │           ├── forecasts.py
│   │   │           ├── models.py
│   │   │           ├── metrics.py
│   │   │           └── risk.py
│   │   ├── schemas/
│   │   ├── services/
│   │   ├── repositories/
│   │   ├── db/
│   │   └── ml/
│   │       ├── registry.py
│   │       ├── loader.py
│   │       ├── cache.py
│   │       └── validation.py
│   ├── ai/
│   │   ├── facts.py
│   │   ├── ollama_client.py
│   │   ├── summary_service.py
│   │   ├── fallback.py
│   │   └── validation.py
│   ├── cli/
│   │   ├── seed_data.py
│   │   ├── import_model.py
│   │   └── activate_model.py
│   ├── migrations/
│   └── tests/
├── frontend/
│   ├── index.html
│   └── assets/
│       ├── css/
│       ├── js/
│       └── vendor/
├── krl_core/                  # dipakai notebook dan backend
│   ├── __init__.py
│   ├── forecast.py            # ForecastBundle ABC + kontrak hasil
│   ├── features.py            # feature engineering bersama
│   ├── lightgbm_bundle.py     # implementasi pipeline LightGBM
│   └── risk.py                # logika risiko bersama
├── artifacts/
│   └── models/<run_id>/
├── docs/
├── src/                       # kode riset; dipertahankan
├── notebooks/
├── data/
└── requirements.txt
```

### Mengapa `krl_core/` diperlukan

Pickle menyimpan **lokasi module** dari class yang di-pickle. Agar `model.pkl` bisa dibuka
di backend, class `ForecastBundle` harus berada di module yang sama saat training dan
serving. Karena itu:

- Notebook mengimpor `krl_core.forecast`.
- Backend juga mengimpor `krl_core.forecast`.
- Keduanya memakai package yang sama, bukan `sys.path.append` yang berbeda.

`src/features.py` yang sudah ada dapat dipertahankan. Logika yang dipakai bersama
dipindahkan atau di-re-export melalui `krl_core/features.py` agar notebook lama tetap
berjalan.

---

## 5. Alur Request Forecast

```text
GET /api/v1/forecasts/latest?horizon=1,2,3,4
        │
        ▼
1. Ambil model run aktif dari model_runs
        │
        ▼
2. Ambil data_version aktif
        │
        ▼
3. Cek Redis shared cache
   key = (model_run_id, data_version, horizons)
        │
        ├── hit  → hitung risiko → response
        │
        └── miss
              │
              ▼
        4. Single-flight lock per key
              │
              ▼
        5. Ambil history dari actuals
           Ambil calendar sampai horizon target
              │
              ▼
        6. Jalankan bundle.predict(history, calendar)
           di threadpool (CPU-bound)
              │
              ▼
        7. Validasi hasil:
           lower <= point <= upper
           interval 80 di dalam interval 95
              │
              ▼
        8. Simpan ke cache
              │
              ▼
        9. Hitung risiko → response
```

### Mengapa per request + cache

- Model tetap satu sumber kebenaran: file pickle dari notebook.
- Tidak perlu menyimpan snapshot forecast di database pada MVP.
- Artifact aktif di-load saat lifespan startup; request pertama hanya menjalankan inference.
- Request berikutnya cepat karena cache.
- Cache key mengandung `data_version` dan `model_run_id`, sehingga cache otomatis
  tidak berlaku saat data atau model berubah.

### Strategi cache

| Item | Nilai awal |
|---|---|
| Implementasi | Redis + lock terdistribusi; LRU lokal kecil sebagai lapisan pertama |
| TTL forecast | 3600 detik |
| TTL AI summary | 24 jam |
| Max entries lokal | 128 |
| Key | `model_run_id:data_version:horizons` |
| Invalidasi | TTL, ganti model aktif, atau data version berubah |

Redis menyimpan cache bersama untuk seluruh worker/container. Gunakan lock Redis dengan TTL
lebih besar dari batas waktu inference agar hanya satu worker menghitung key yang sama.
Cache lokal bersifat optimasi saja dan tidak menjadi sumber kebenaran.

### Concurrency

- Inference dijalankan dengan `run_in_threadpool` agar event loop tidak terblokir.
- Gunakan Redis lock per key untuk mencegah **cache stampede** lintas worker.
- Batas waktu inference: `KRL_INFERENCE_TIMEOUT_SECONDS` (default 15 detik).
- Jika timeout atau gagal: `503 Service Unavailable` dengan kode error yang jelas.

---

## 6. Alur Import Model

Import dilakukan lewat CLI, bukan endpoint API pada MVP.

```bash
python -m backend.cli.import_model --path artifacts/models/<run_id>
```

Langkah:

1. Baca `manifest.json`.
2. Validasi field wajib dan versi schema.
3. Hitung checksum `model.pkl`, bandingkan dengan manifest.
4. Load pickle di proses terpisah.
5. Pastikan object adalah instance `ForecastBundle`.
6. Simpan metadata ke `model_runs` dengan status `inactive`.
7. Jalankan smoke test inference dengan data terakhir.
8. Validasi hasil smoke test.
9. Aktifkan model:

```bash
python -m backend.cli.activate_model --run-id <run_id>
```

Aktivasi harus atomik:

```sql
UPDATE model_runs SET is_active = false;
UPDATE model_runs SET is_active = true WHERE run_id = :run_id;
```

Dijaga partial unique index agar hanya satu model aktif.

---

## 7. Skema Database

Semua waktu memakai `TIMESTAMPTZ` UTC. Semua periode disimpan sebagai `DATE` tanggal 1.

### `actuals`

```sql
CREATE TABLE actuals (
    period       DATE PRIMARY KEY,
    value_ribu   NUMERIC(14, 2) NOT NULL CHECK (value_ribu > 0),
    is_imputed   BOOLEAN NOT NULL DEFAULT FALSE,
    source       TEXT NOT NULL DEFAULT 'BPS',
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### `calendar`

```sql
CREATE TABLE calendar (
    period                         DATE PRIMARY KEY,
    total_hari                     SMALLINT NOT NULL,
    jumlah_hari_kerja              SMALLINT NOT NULL,
    jumlah_libur_nasional_weekday  SMALLINT NOT NULL,
    is_lebaran                     BOOLEAN NOT NULL,
    is_covid                       BOOLEAN NOT NULL,
    is_actual                      BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at                     TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

`is_actual = true` untuk bulan yang sudah punya data aktual. Bulan masa depan tetap
disimpan agar backend bisa membangun fitur kalender sampai horizon target.

### `data_versions`

```sql
CREATE TABLE data_versions (
    id            UUID PRIMARY KEY,
    version_hash  TEXT NOT NULL UNIQUE,
    row_count     INTEGER NOT NULL,
    min_period    DATE NOT NULL,
    max_period    DATE NOT NULL,
    source        TEXT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_active     BOOLEAN NOT NULL DEFAULT FALSE
);
```

Hanya satu data version aktif.

### `model_runs`

```sql
CREATE TABLE model_runs (
    id                UUID PRIMARY KEY,
    run_id            TEXT NOT NULL UNIQUE,
    algorithm         TEXT NOT NULL,
    model_version     TEXT NOT NULL,
    schema_version    TEXT NOT NULL,
    data_start        DATE NOT NULL,
    data_end          DATE NOT NULL,
    horizon_max       INTEGER NOT NULL CHECK (horizon_max BETWEEN 1 AND 12),
    artifact_path     TEXT NOT NULL,
    checksum          TEXT NOT NULL,
    library_versions  JSONB NOT NULL,
    model_card        JSONB NOT NULL,
    trained_at        TIMESTAMPTZ NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_active         BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE UNIQUE INDEX one_active_model
    ON model_runs (is_active)
    WHERE is_active = TRUE;
```

### `metrics`

```sql
CREATE TABLE metrics (
    id             UUID PRIMARY KEY,
    model_run_id   UUID NOT NULL REFERENCES model_runs(id) ON DELETE CASCADE,
    subset         TEXT NOT NULL,
    horizon        INTEGER,
    n              INTEGER NOT NULL,
    mae            NUMERIC(14, 4),
    rmse           NUMERIC(14, 4),
    mase           NUMERIC(14, 4),
    picp80         NUMERIC(8, 4),
    picp95         NUMERIC(8, 4),
    mpiw80         NUMERIC(14, 4),
    mpiw95         NUMERIC(14, 4),
    winkler80      NUMERIC(14, 4),
    winkler95      NUMERIC(14, 4),
    UNIQUE (model_run_id, subset, horizon)
);
```

### Tabel opsional (fase lanjutan)

- `forecast_snapshots` — cache bersama/audit forecast.
- `ai_summaries` — tidak dipakai pada MVP; insight hanya berada di Redis sampai TTL berakhir.
- `audit_logs` — catatan aksi admin.
- `jobs` — status retrain/import jika nanti ada endpoint admin.

---

## 8. Kontrak API

Base path: `/api/v1`.

### Public

| Method | Endpoint | Fungsi |
|---|---|---|
| GET | `/health/live` | Liveness |
| GET | `/health/ready` | Cek PostgreSQL + model aktif |
| GET | `/meta` | Rentang data, model aktif, horizon tersedia |
| GET | `/passengers` | Data historis, filter `start`, `end`, `limit` |
| GET | `/passengers/{period}` | Satu bulan historis |
| GET | `/forecasts/latest` | Forecast terbaru + interval |
| GET | `/models` | Daftar model run |
| GET | `/models/{run_id}` | Model card |
| GET | `/metrics` | Metrik evaluasi, filter `model_run_id`, `subset`, `horizon` |
| GET | `/risk/latest` | Risiko berdasarkan kapasitas env |
| POST | `/risk/simulate` | Simulasi kapasitas/horizon |
| GET | `/insights/latest` | Summary dan rekomendasi AI untuk forecast aktif |
| POST | `/insights/simulate` | Summary AI dari simulasi kapasitas |

### Admin (disiapkan, belum MVP)

| Method | Endpoint | Fungsi |
|---|---|---|
| POST | `/admin/import-model` | Import artifact (opsional fase lanjutan) |
| POST | `/admin/activate-model/{run_id}` | Aktifkan model |
| POST | `/admin/cache/clear` | Bersihkan cache |
| POST | `/admin/data/refresh` | Upload data baru |
| POST | `/admin/retrain` | Trigger training (di luar backend) |

Semua endpoint admin memakai header:

```http
X-API-Key: <KRL_API_KEY>
```

### Contoh `GET /forecasts/latest`

```json
{
  "data": [
    {
      "period": "2026-09",
      "horizon": 1,
      "point": 30500.0,
      "intervals": {
        "80": { "lower": 29500.0, "upper": 31500.0 },
        "95": { "lower": 28800.0, "upper": 32200.0 }
      },
      "risk": {
        "status": "waspada",
        "utilization": 0.973,
        "capacity_ribu": 32384.0,
        "basis": "upper95"
      }
    }
  ],
  "meta": {
    "model_run_id": "lgbm_cqr_20261028_120000",
    "algorithm": "lightgbm_cqr",
    "data_version": "a1b2c3d4",
    "data_through": "2026-08",
    "generated_at": "2026-10-28T12:00:00Z",
    "cached": false,
    "unit": "ribu_orang",
    "available_horizons": [1, 2, 3, 4]
  }
}
```

### Contoh `POST /risk/simulate`

Request:

```json
{
  "capacity_weekday_ribu": 1200,
  "capacity_weekend_ribu": 800,
  "level": 95,
  "horizons": [1, 2, 3, 4]
}
```

Response:

```json
{
  "data": [
    {
      "period": "2026-09",
      "horizon": 1,
      "upper": 31500.0,
      "capacity_ribu": 32384.0,
      "utilization": 0.973,
      "status": "waspada"
    }
  ],
  "meta": {
    "level": 95,
    "formula": "weekday_weekend_split",
    "generated_at": "2026-10-28T12:00:00Z"
  }
}
```

### Format Error (RFC 7807)

```json
{
  "type": "https://krl-forecast.local/errors/horizon-not-available",
  "title": "Horizon not available",
  "status": 422,
  "detail": "Horizon 5 tidak tersedia. Kalender hanya sampai 2026-12.",
  "instance": "/api/v1/forecasts/latest",
  "request_id": "01J..."
}
```

Kode error yang direncanakan:

| Kode | HTTP | Kondisi |
|---|---|---|
| `MODEL_NOT_AVAILABLE` | 503 | Belum ada model aktif |
| `MODEL_LOAD_FAILED` | 503 | Pickle gagal dimuat |
| `INFERENCE_FAILED` | 503 | Prediksi gagal/timeout |
| `HORIZON_NOT_AVAILABLE` | 422 | Horizon di luar kalender/model |
| `CALENDAR_INCOMPLETE` | 503 | Kalender target belum ada |
| `CAPACITY_NOT_CONFIGURED` | 200 + status | Risiko tidak bisa dihitung |
| `UNAUTHORIZED` | 401 | API key admin salah |

---

## 9. Kapasitas dan Risiko

### Rumus

```text
hari_libur = total_hari - jumlah_hari_kerja

kapasitas_bulanan =
    kapasitas_harian_kerja × jumlah_hari_kerja
  + kapasitas_harian_libur × hari_libur

utilization = upper95 / kapasitas_bulanan
```

### Status

| Status | Kondisi |
|---|---|
| `aman` | `utilization < 0.90` |
| `waspada` | `0.90 <= utilization < 1.00` |
| `kritis` | `utilization >= 1.00` |
| `belum_ditentukan` | kapasitas belum diisi |

### Konfigurasi

```env
KRL_CAPACITY_WEEKDAY_RIBU=
KRL_CAPACITY_WEEKEND_RIBU=
KRL_RISK_WASPADA_RATIO=0.90
```

Jika nilai kapasitas kosong:

- `GET /risk/latest` tetap `200`.
- Setiap item mengembalikan `status: "belum_ditentukan"` dan `reason`.
- `POST /risk/simulate` tetap bisa dipakai dengan parameter kapasitas eksplisit.

### Catatan domain

- `hari_libur` di sini adalah hari non-kerja kalender, bukan hanya libur nasional.
- Rumus ini adalah asumsi; dokumentasikan di README dan model card.
- Analisis sensitivitas (`±5%`, `±10%`) dapat ditambahkan di endpoint simulasi.

---

## 10. Keamanan

- Public read: tanpa auth.
- Admin: `X-API-Key`, dibandingkan dengan `secrets.compare_digest`.
- API key disimpan di env, tidak di repo.
- Pickle hanya dimuat dari path yang dikontrol (`artifacts/models/`), bukan upload user.
- Validasi checksum sebelum load.
- CORS:

```env
CORS_ORIGINS=http://localhost:8000,http://127.0.0.1:8000
```

- Rate limit endpoint publik dengan `slowapi`.
- Batas ukuran request untuk endpoint admin (fase lanjutan).
- Jangan pernah mengaktifkan `allow_pickle` pada input yang tidak tepercaya.
- Ollama hanya boleh dapat diakses melalui jaringan internal Docker, bukan port publik.
- Endpoint insight tidak menerima prompt bebas pengguna pada MVP.

---

## 11. Observability

- Log JSON terstruktur: `timestamp`, `level`, `request_id`, `method`, `path`,
  `status_code`, `duration_ms`, `model_run_id`.
- `X-Request-ID` dibuat jika tidak ada.
- `/health/live`: proses hidup.
- `/health/ready`: PostgreSQL reachable + model aktif ada + file artifact ada.
- Metrik inference: durasi, cache hit/miss, error count.
- Metrik AI: durasi Ollama, cache hit/miss, fallback count, kegagalan schema, dan circuit-breaker state.
- Opsional fase lanjutan: Prometheus `/metrics`, Sentry.

---

## 12. Frontend Statis

- Lokasi: `frontend/`.
- Disajikan oleh FastAPI:

```python
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
```

- Mount dilakukan **setelah** router API dan route dokumentasi.
- API base URL: `/api/v1`.
- Chart.js disimpan lokal di `frontend/assets/vendor/` agar tidak bergantung CDN.
- Halaman minimal:
  1. Ringkasan: data terakhir, model aktif, status risiko.
  2. Grafik historis + forecast dengan pita interval.
  3. Tabel forecast per horizon.
  4. Tabel metrik dan model card.
  5. Form simulasi kapasitas.

---

## 13. Deployment

### Docker Compose

```text
services:
  db:
    image: postgres:16-alpine
    volume: pgdata
    healthcheck: pg_isready

  api:
    build: ./backend
    env_file: .env
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
      ollama-pull:
        condition: service_completed_successfully
    ports:
      - "8000:8000"
    volumes:
      - ./artifacts:/app/artifacts:ro

  redis:
    image: redis:7-alpine
    volumes:
      - redisdata:/data
    healthcheck: redis-cli ping

  ollama:
    image: ollama/ollama:<PINNED_VERSION>
    volumes:
      - ollama:/root/.ollama
    # Tidak publish port: hanya jaringan internal Compose.

  ollama-pull:
    image: ollama/ollama:<PINNED_VERSION>
    environment:
      OLLAMA_HOST: http://ollama:11434
      OLLAMA_MODEL: qwen3.5:4b
    depends_on:
      ollama:
        condition: service_started
    command: ["sh", "-c", "until ollama list >/dev/null 2>&1; do sleep 2; done; ollama pull \"$OLLAMA_MODEL\""]
```

### Dockerfile

- Base image harus **sama** dengan environment training (Python version).
- Install `libgomp1` untuk LightGBM.
- Install dependencies dari `requirements.lock`.
- Jalankan sebagai non-root.
- Healthcheck ke `/api/v1/health/live`.
- Ollama menggunakan volume persisten dan `ollama-pull` memastikan `qwen3.5:4b` tersedia
  sebelum API menerima request insight.

### Migrasi

Migrasi dijalankan terpisah, bukan otomatis di startup:

```bash
alembic upgrade head
```

### Seed data

```bash
python -m backend.cli.seed_data
python -m backend.cli.import_model --path artifacts/models/<run_id>
python -m backend.cli.activate_model --run-id <run_id>
```

---

## 14. Testing

| Jenis | Cakupan |
|---|---|
| Unit | Rumus kapasitas, status risiko, validasi interval, cache key |
| Unit | `ForecastBundle` contract dengan fake bundle |
| Integration | Endpoint dengan PostgreSQL test + fake model |
| Integration | Import model: manifest, checksum, aktivasi |
| Concurrency | Dua request bersamaan hanya menghasilkan satu inference |
| Resilience | Ollama timeout, circuit breaker, dan deterministic fallback |
| AI safety | Citation fact-id valid; AI tidak dapat mengubah risk status |
| Contract | Snapshot OpenAPI |
| Data | Seed 128 observasi, period kontinu, kalender lengkap |

Target minimal: **80% coverage** untuk service dan validator.

---

## 15. Roadmap

| Fase | Deliverable | Kriteria selesai |
|---|---|---|
| 0 | Dokumen arsitektur + kontrak artifact | Disetujui |
| 1 | Scaffold backend, config, logging, error, health | `uvicorn` jalan, `/docs` terbuka |
| 2 | PostgreSQL, Alembic, seed actuals/calendar | `alembic upgrade head` + seed sukses |
| 3 | `krl_core` + `ForecastBundle` + fake bundle | Pickle bisa dibuat dan dimuat |
| 4 | Model registry, preload, Redis cache, inference service | Smoke test inference lolos |
| 5 | Endpoint history, forecast, models, metrics, risk | Semua test integration lolos |
| 6 | AI insight service + fallback + audit | Output terstruktur dan grounded lolos test |
| 7 | Frontend statis + simulasi | Halaman utama menampilkan data |
| 8 | Docker Compose, CI, rate limit, dokumentasi | `docker compose up` sukses |

Estimasi backend: **9–12 hari kerja**, di luar pembuatan notebook `05`/`06`.

---

## 16. Risiko dan Mitigasi

| Risiko | Dampak | Mitigasi |
|---|---|---|
| Pickle tidak kompatibel | Model gagal load | Pin versi Python/library, checksum, smoke test |
| Kalender hanya sampai 2026-12 | Horizon 5–6 gagal | `available_horizons` dinamis, generate kalender 2027 |
| Inference lambat saat request pertama | Latency tinggi | Preload model, cache, timeout, threadpool |
| Cache stampede | Inference berulang | Single-flight lock per key |
| Ollama lambat/gagal | Insight tidak tersedia | Timeout, circuit breaker, Redis cache, fallback deterministik |
| Halusinasi AI | Rekomendasi tidak dapat dipercaya | Fact pack, schema ketat, citation ID, action catalog, disclaimer |
| Kapasitas belum diisi | Risiko tidak bisa dihitung | Status `belum_ditentukan`, simulasi manual |
| Data BPS berubah | Forecast tidak konsisten | `data_versions`, cache key, audit |
| Pickle berbahaya | RCE jika file tidak tepercaya | Hanya load artifact tepercaya, checksum, admin-only |

---

## 17. Open Items

1. Nilai `KRL_CAPACITY_WEEKDAY_RIBU` dan `KRL_CAPACITY_WEEKEND_RIBU` belum diisi.
2. Kalender 2027 belum tersedia; horizon maksimum saat ini 4 bulan.
3. Implementasi `ForecastBundle` menunggu notebook `05`/`06`.
4. Apakah frontend perlu halaman admin, atau cukup read-only pada MVP?
5. Apakah endpoint `/models` perlu menampilkan riwayat semua run atau hanya aktif?
