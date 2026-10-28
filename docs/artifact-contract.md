# Kontrak Artifact Model

Dokumen ini mengikat notebook training dan backend FastAPI. Tujuannya agar
`model.pkl` yang dihasilkan notebook bisa dimuat dan dipakai backend tanpa
menebak-nebak struktur internalnya.

Status: **draft**, mengikuti keputusan `ForecastBundle` sebagai pipeline object.

---

## 1. Prinsip

1. Notebook adalah satu-satunya tempat training dan kalibrasi interval.
2. Backend tidak melatih ulang model.
3. Backend hanya memanggil method `predict()` dari object yang sudah di-pickle.
4. Semua input yang dibutuhkan `predict()` berasal dari database:
   - history aktual
   - kalender sampai horizon target
5. Semua output divalidasi sebelum dikembalikan ke client.
6. Class `ForecastBundle` harus berada di package yang sama di notebook dan backend.

---

## 2. Package Bersama: `krl_core`

Pickle menyimpan referensi module. Jika notebook menyimpan object dari module
`serving` tetapi backend mengimpornya sebagai `src.serving`, unpickle akan gagal.

Karena itu, class dan implementasi harus berada di package `krl_core`:

```text
krl_core/
├── __init__.py
├── forecast.py          # ForecastBundle ABC, ForecastResult
├── features.py          # feature engineering bersama
├── lightgbm_bundle.py   # implementasi LightGBM + conformal
└── risk.py              # logika risiko bersama
```

Notebook:

```python
from krl_core.lightgbm_bundle import LightGBMForecastBundle
```

Backend:

```python
from krl_core.forecast import ForecastBundle
```

Keduanya harus menginstall package yang sama, misalnya:

```bash
pip install -e .
```

atau menambahkan root repo ke `PYTHONPATH`.

---

## 3. Interface `ForecastBundle`

```python
# krl_core/forecast.py
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class ForecastRow:
    period: str          # YYYY-MM
    horizon: int         # 1..horizon_max
    point: float
    lower80: float
    upper80: float
    lower95: float
    upper95: float


class ForecastBundle(ABC):
    schema_version: str = "1.0"
    run_id: str
    algorithm: str
    horizon_max: int
    target: str = "penumpang_ribu"

    @abstractmethod
    def predict(
        self,
        history: pd.Series,
        calendar: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Menghasilkan forecast untuk bulan-bulan setelah history terakhir.

        Parameters
        ----------
        history:
            Series dengan index DatetimeIndex bulanan (frekuensi MS),
            nilai dalam satuan ribu orang, sudah diurutkan naik.
            Contoh:
                2026-06-01    30468.0
                2026-07-01    32467.0
                2026-08-01    30135.0

        calendar:
            DataFrame dengan index DatetimeIndex bulanan.
            Harus mencakup bulan target, yaitu setelah history terakhir
            sampai minimal history.index.max() + horizon_max bulan.
            Kolom wajib:
                total_hari
                jumlah_hari_kerja
                jumlah_libur_nasional_weekday
                is_lebaran
                is_covid

        Returns
        -------
        DataFrame dengan kolom:
            period, horizon, point, lower80, upper80, lower95, upper95
        Satu baris per horizon.
        """
```

### Alasan input `calendar` terpisah

Backend tidak perlu tahu cara membuat fitur Lebaran lag/lead, hari kerja, atau
musim. Semua itu tanggung jawab `ForecastBundle`. Backend hanya menyediakan
kalender mentah yang sudah tersedia di database.

### Alasan output DataFrame

- Format stabil dan mudah divalidasi dengan Pydantic.
- Tidak bergantung pada tipe model.
- Mudah disimpan, di-cache, dan diuji.

---

## 4. Implementasi LightGBM yang Diharapkan

Notebook `05_lightgbm_conformal.ipynb` dapat membuat subclass:

```python
# krl_core/lightgbm_bundle.py
class LightGBMForecastBundle(ForecastBundle):
    def __init__(
        self,
        run_id: str,
        models: dict[int, object],
        conformal: dict[int, dict[str, dict[str, float]]],
        feature_columns: list[str],
        horizon_max: int,
        target: str = "penumpang_ribu",
    ):
        ...
```

Isi internal bebas, tetapi `predict()` harus:

1. Membangun fitur untuk setiap horizon dari `history` + `calendar`.
2. Memanggil model horizon yang sesuai.
3. Menambahkan lebar interval conformal.
4. Mengembalikan DataFrame sesuai kontrak.

### Larangan

- Jangan mengembalikan `NaN` atau `inf`.
- Jangan mengembalikan periode yang sudah ada di `history`.
- Jangan mengembalikan horizon tidak berurutan.
- Jangan mengubah nilai history dari dalam `predict()`.

---

## 5. Struktur Folder Artifact

```text
artifacts/models/<run_id>/
├── model.pkl
├── manifest.json
└── model_card.json
```

`model.pkl` berisi object `ForecastBundle`.

`manifest.json` dan `model_card.json` **wajib JSON**, bukan pickle, agar bisa
dibaca tanpa mengeksekusi kode Python.

---

## 6. `manifest.json`

```json
{
  "schema_version": "1.0",
  "run_id": "lgbm_cqr_20261028_120000",
  "algorithm": "lightgbm_cqr",
  "model_version": "1.0.0",
  "created_at": "2026-10-28T12:00:00Z",
  "data_start": "2016-01",
  "data_through": "2026-08",
  "horizon_max": 4,
  "target": "penumpang_ribu",
  "unit": "ribu_orang",
  "git_sha": "044fee2",
  "python_version": "3.12.7",
  "library_versions": {
    "pandas": "2.2.3",
    "numpy": "2.1.1",
    "lightgbm": "4.5.0",
    "statsmodels": "0.14.4",
    "scikit-learn": "1.5.2",
    "joblib": "1.4.2"
  },
  "files": {
    "model.pkl": {
      "sha256": "...",
      "size_bytes": 123456
    }
  }
}
```

Field wajib:

| Field | Tipe | Keterangan |
|---|---|---|
| `schema_version` | string | Versi kontrak artifact |
| `run_id` | string | Unik, dipakai sebagai identitas model |
| `algorithm` | string | `lightgbm_cqr`, `sarimax`, dsb. |
| `model_version` | string | Versi logika model |
| `created_at` | ISO 8601 | Waktu export |
| `data_start` | `YYYY-MM` | Awal data training |
| `data_through` | `YYYY-MM` | Akhir data training |
| `horizon_max` | int | 1..12 |
| `target` | string | `penumpang_ribu` |
| `unit` | string | `ribu_orang` |
| `python_version` | string | Versi Python training |
| `library_versions` | object | Versi library training |
| `files.model.pkl.sha256` | string | Checksum |

`run_id` disarankan:

```text
<algorithm>_<YYYYMMDD>_<HHMMSS>
```

Contoh: `lgbm_cqr_20261028_120000`.

---

## 7. `model_card.json`

```json
{
  "run_id": "lgbm_cqr_20261028_120000",
  "algorithm": "lightgbm_cqr",
  "description": "LightGBM quantile + conformalized quantile regression",
  "training": {
    "data_start": "2016-01",
    "data_through": "2026-08",
    "n_observations": 128,
    "covid_handling": "covid flag + evaluasi subset bersih"
  },
  "features": [
    "y_lag0",
    "y_lag1",
    "y_lag2",
    "y_tahun_lalu",
    "roll_mean_3",
    "roll_mean_12",
    "bulan_sin",
    "bulan_cos",
    "jumlah_hari_kerja",
    "selisih_hari_kerja_vs_tahun_lalu",
    "is_lebaran",
    "lebaran_lag1",
    "lebaran_lead1",
    "is_covid"
  ],
  "hyperparameters": {
    "n_estimators": 500,
    "learning_rate": 0.03,
    "num_leaves": 15
  },
  "conformal": {
    "method": "cqr",
    "levels": [0.80, 0.95],
    "calibration": "residual out-of-sample per horizon"
  },
  "metrics_summary": {
    "subset": "bersih",
    "mase": 0.78,
    "picp80": 0.81,
    "picp95": 0.94
  },
  "limitations": [
    "Sampel kecil (128 observasi bulanan).",
    "Kalender hanya sampai 2026-12.",
    "Ambang kapasitas adalah asumsi."
  ]
}
```

---

## 8. Validasi Wajib

### Saat import

Backend wajib memeriksa:

1. `manifest.json` valid dan field wajib lengkap.
2. `schema_version` didukung.
3. Checksum `model.pkl` cocok.
4. `model.pkl` bisa di-load.
5. Object adalah instance `ForecastBundle`.
6. `bundle.run_id == manifest.run_id`.
7. `bundle.horizon_max == manifest.horizon_max`.
8. Versi Python dan library sesuai environment backend.
9. Smoke test `predict()` dengan data terakhir berhasil.

### Saat `predict()`

Backend wajib memeriksa:

1. Jumlah baris = `horizon_max`.
2. `horizon` berurutan `1..horizon_max`.
3. `period` sesuai `history.index.max() + h bulan`.
4. Tidak ada `NaN`/`inf`.
5. `lower80 <= point <= upper80`.
6. `lower95 <= point <= upper95`.
7. `lower95 <= lower80` dan `upper80 <= upper95`.
8. Nilai positif.

Jika gagal: `503 INFERENCE_FAILED`, log detail, jangan cache hasil rusak.

---

## 9. Kompatibilitas Versi

Pickle tidak portabel antar versi Python/library. Aturan:

- Python training = Python Docker backend.
- Versi `pandas`, `numpy`, `lightgbm`, `statsmodels`, `scikit-learn`, `joblib`
  harus sama persis.
- Simpan `requirements.lock` dari environment training.
- Catat versi di `manifest.json`.
- Docker image backend dibangun dari lock yang sama.

Jika versi berbeda:

- Import model ditolak dengan pesan yang jelas.
- Jangan mencoba memuat paksa, karena hasil prediksi bisa berubah.

---

## 10. Keamanan Pickle

Pickle dapat mengeksekusi kode saat dimuat. Karena itu:

- Hanya load file dari `artifacts/models/` yang dikontrol repo/admin.
- Jangan pernah load pickle dari upload user.
- Verifikasi checksum sebelum load.
- Jalankan import di proses terpisah dari web server.
- Di produksi, artifact sebaiknya read-only.

---

## 11. Contoh Export dari Notebook

```python
import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone

import joblib

from krl_core.lightgbm_bundle import LightGBMForecastBundle

RUN_ID = "lgbm_cqr_20261028_120000"
OUT = Path("../artifacts/models") / RUN_ID
OUT.mkdir(parents=True, exist_ok=True)

bundle = LightGBMForecastBundle(
    run_id=RUN_ID,
    models=models,
    conformal=conformal,
    feature_columns=feature_columns,
    horizon_max=4,
    target="penumpang_ribu",
)

model_path = OUT / "model.pkl"
joblib.dump(bundle, model_path)

sha256 = hashlib.sha256(model_path.read_bytes()).hexdigest()

manifest = {
    "schema_version": "1.0",
    "run_id": RUN_ID,
    "algorithm": "lightgbm_cqr",
    "model_version": "1.0.0",
    "created_at": datetime.now(timezone.utc).isoformat(),
    "data_start": "2016-01",
    "data_through": "2026-08",
    "horizon_max": 4,
    "target": "penumpang_ribu",
    "unit": "ribu_orang",
    "python_version": "3.12.7",
    "library_versions": {...},
    "files": {
        "model.pkl": {
            "sha256": sha256,
            "size_bytes": model_path.stat().st_size,
        }
    },
}

(OUT / "manifest.json").write_text(
    json.dumps(manifest, indent=2, ensure_ascii=False),
    encoding="utf-8",
)
```

---

## 12. Checklist Notebook Sebelum Export

- [ ] `ForecastBundle` diimpor dari `krl_core`, bukan module lokal notebook.
- [ ] `run_id` unik.
- [ ] `horizon_max` sesuai kalender yang tersedia.
- [ ] Interval 80 dan 95 sudah dikalibrasi.
- [ ] `predict()` tidak memakai data setelah origin.
- [ ] `predict()` idempoten untuk input yang sama.
- [ ] Smoke test pada data terakhir berhasil.
- [ ] `manifest.json` berisi versi Python dan library.
- [ ] Checksum `model.pkl` dihitung setelah file selesai ditulis.
- [ ] `model_card.json` berisi metrik dan keterbatasan.
- [ ] Tidak ada path absolut mesin lokal di dalam artifact.
