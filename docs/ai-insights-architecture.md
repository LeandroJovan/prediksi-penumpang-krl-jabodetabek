# Arsitektur AI Insight

Status: **draft**. Dokumen ini melengkapi `architecture.md`.

## Keputusan

| Aspek | Keputusan |
|---|---|
| Runtime AI | Ollama lokal di Docker Compose |
| Model | `qwen3.5:4b` |
| Resource target | CPU saja, RAM 8–16 GB |
| Bahasa | Indonesia (`id`) dan Inggris (`en`) |
| Trigger | On-demand dengan cache Redis |
| Input AI | Fakta agregat dari backend saja |
| Peran AI | Narasi dan rekomendasi berbasis fakta |
| Input pengguna | Tidak ada prompt bebas pada MVP |
| Jika AI gagal | Fallback deterministik tetap tersedia |

## Batas Tanggung Jawab

`ForecastService` menghitung forecast dan interval. `RiskService` menghitung kapasitas,
utilisasi, serta status `aman`/`waspada`/`kritis`. AI hanya menjelaskan hasil tersebut.

AI dilarang mengubah angka, interval, kapasitas, atau status risiko; membuat klaim
sebab-akibat yang tidak ada di fakta; menjalankan tool/SQL; atau menerima prompt bebas.

## Alur

```text
GET /api/v1/insights/latest?language=id
        │
        ▼
ForecastService + RiskService
        │
        ▼
FactPackBuilder (JSON agregat, versioned)
        │
        ▼
Redis: ai:v1:<hash>
  hit ──► response
  miss
        ▼
OllamaClient (timeout + circuit breaker)
        │
        ▼
Pydantic schema + citation/action validation
        │
        ├── valid ──► cache Redis → source=ollama
        └── error ──► deterministic fallback → source=fallback
```

Forecast API harus tetap siap jika Ollama mati. Endpoint insight memakai fallback dan
tidak menjadikan readiness forecast gagal.

## Fact Pack Tepercaya

Hanya backend yang membentuk fact pack. Data mentah, kredensial, dan data personal tidak
dikirim ke model.

```json
{
  "schema_version": "1.0",
  "language": "id",
  "context": {"model_run_id": "lgbm_cqr_...", "data_through": "2026-08", "unit": "ribu_orang"},
  "facts": [
    {"id": "F1", "kind": "forecast", "period": "2026-09", "horizon": 1, "point": 30500.0, "lower95": 28800.0, "upper95": 32200.0},
    {"id": "F2", "kind": "risk", "period": "2026-09", "status": "waspada", "utilization": 0.973, "capacity_ribu": 32384.0, "basis": "upper95"},
    {"id": "F3", "kind": "model_metric", "subset": "bersih", "mase": 0.78, "picp95": 0.94}
  ],
  "allowed_actions": ["monitor_capacity", "review_operational_readiness", "prepare_contingency_plan", "review_capacity_assumption"]
}
```

Cache key adalah SHA-256 dari canonical fact pack, `prompt_version`, `OLLAMA_MODEL`, dan
`language`. Perubahan model/data/kapasitas/prompt otomatis menghasilkan key baru.

## Kontrak Output LLM

Ollama diminta menghasilkan JSON saja. Backend memvalidasi output sebelum dikirim.

```json
{
  "risk_status": "waspada",
  "headline": "Risiko kapasitas September 2026 berada pada status waspada.",
  "summary": "Forecast dan interval menunjukkan kebutuhan pemantauan kapasitas.",
  "recommendations": [
    {"action": "monitor_capacity", "priority": "medium", "rationale": "Pantau realisasi terhadap batas atas interval.", "fact_ids": ["F1", "F2"]}
  ],
  "limitations": ["Interval prediksi menunjukkan ketidakpastian."],
  "fact_ids": ["F1", "F2", "F3"]
}
```

Validasi wajib:

1. JSON valid dan sesuai Pydantic schema.
2. Setiap `fact_id` ada di fact pack.
3. `action` terdapat di `allowed_actions`.
4. `priority` hanya `low`, `medium`, atau `high`.
5. Maksimal 3 rekomendasi dan 500 karakter output per bahasa.
6. `risk_status` harus cocok persis dengan fakta risiko. Jika gagal, gunakan fallback.
7. Response selalu memuat `source: ollama` atau `source: fallback`.

UI merender angka dan badge status dari endpoint forecast/risk atau field tervalidasi,
bukan dengan menafsirkan teks LLM.

## Endpoint

| Method | Endpoint | Fungsi |
|---|---|---|
| GET | `/api/v1/insights/latest?language=id|en` | Insight forecast aktif |
| POST | `/api/v1/insights/simulate` | Insight hasil simulasi kapasitas |

`refresh=true` mengabaikan cache dan hanya tersedia untuk admin. Endpoint simulasi diberi
rate limit lebih ketat daripada endpoint baca biasa.

## Performa dan Resilience

| Kontrol | Nilai awal |
|---|---|
| TTL Redis insight | 24 jam |
| Timeout Ollama | 12 detik |
| Retry sinkron | Tidak ada |
| Circuit breaker | 3 kegagalan/60 detik, cooldown 60 detik |
| Concurrency Ollama | Semaphore 1 per API instance |
| Rate limit insight | 10 request/menit/IP |
| Fallback | Selalu tersedia tanpa Ollama |

Ollama hanya berada pada jaringan internal Compose. Service `ollama-pull` memastikan
`qwen3.5:4b` diunduh ke volume persisten sebelum API berjalan. Port Ollama tidak dipublish.

## Konfigurasi

```env
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=qwen3.5:4b
OLLAMA_TIMEOUT_SECONDS=12
OLLAMA_MAX_CONCURRENCY=1
AI_INSIGHT_CACHE_TTL_SECONDS=86400
AI_INSIGHT_MAX_OUTPUT_CHARS=500
OLLAMA_NUM_PREDICT=256
OLLAMA_NUM_CTX=2048
AI_INSIGHT_PROMPT_VERSION=1.0
```

## Testing

- Unit: fact pack, cache key, fallback Indonesia/Inggris.
- Unit: validator menolak fact ID, action, atau risk status yang tidak sah.
- Integration: Ollama mock mengembalikan JSON valid, malformed JSON, dan timeout.
- Integration: forecast API tetap `200` saat Ollama mati.
- Load: cache hit tidak memanggil Ollama dan concurrency dibatasi satu semaphore.
