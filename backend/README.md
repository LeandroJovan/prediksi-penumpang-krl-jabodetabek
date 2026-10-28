# KRL Forecast Backend

FastAPI untuk data historis, inference `ForecastBundle`, risiko, dan AI insight Ollama.

## Docker

1. Salin `backend/.env.example` menjadi `backend/.env`, lalu ubah password dan API key.
2. Jalankan `docker compose up --build -d` dari root repository.
3. Seed data awal dengan `docker compose exec api python -m backend.cli.seed_data`.
4. Buka `http://localhost:8000/docs`.

`ollama-pull` mengunduh `qwen3.5:4b` ke volume Docker sebelum API menerima request.

## Status MVP

Endpoint: health, meta, passengers, forecasts, models, metrics, risk, dan insights.
Forecast membutuhkan `model_runs` aktif dan bundle valid di `artifacts/models/<run_id>/`.

Runtime dipin ke Python 3.12 untuk kompatibilitas pickle. Seed membuat tabel awal dari
SQLAlchemy metadata; Alembic migration perlu ditambahkan sebelum deployment produksi.
