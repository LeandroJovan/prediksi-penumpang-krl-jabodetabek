# Panduan Integrasi Back-End & Front-End
## Proyek Sistem Cerdas: Prediksi Penumpang KRL Jabodetabek

Dokumen ini disusun oleh **Machine Learning Engineer** sebagai panduan teknis (*handover documentation*) bagi pengembang **Back-End** dan **Front-End** dalam mengonsumsi model, menyajikan API, serta mendesain antarmuka pengguna (UI/UX) sistem peramalan dan mitigasi risiko kapasitas KRL.

---

## 1. Arsitektur Alur Data (Data Flow Architecture)

```
┌────────────────────────────────────────────────────────────────────────┐
│                        ALUR DATA DAN INTEGRASI                         │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
     ┌─────────────────────────────────────────────────────────────┐
     │                      DATA SOURCES (data/)                   │
     │  - Data Historis Aktual BPS (data/processed/data_final.csv) │
     │  - Data Kalender Eksogen (kalender_fitur.csv)               │
     └──────────────────────────────┬──────────────────────────────┘
                                    │
                                    ▼
     ┌─────────────────────────────────────────────────────────────┐
     │                    BACK-END PIPELINE (src/)                 │
     │  - features.py : Penyiapan lag, rolling mean & kalender     │
     │  - models.py   : Inference SARIMAX & LightGBM Multi-Horizon │
     │  - risk.py     : Decision layer (Aman, Waspada, Kritis)     │
     │  - config.py   : Ambang kapasitas & parameter global        │
     └──────────────────────────────┬──────────────────────────────┘
                                    │
                                    ▼  [Data Contract / JSON Schema]
     ┌─────────────────────────────────────────────────────────────┐
     │                     FRONT-END LAYER (app/)                  │
     │  - Streamlit Dashboard (app/app.py)                         │
     │  - Komponen: KPI Cards, Pita Interval, Alert Warna Risiko  │
     │  - Kontrol Interaktif: Slider Kapasitas & Level Interval   │
     └─────────────────────────────────────────────────────────────┘
```

---

## 2. Petunjuk Khusus untuk Pengembang Back-End

### A. Modul Utama yang Harus Digunakan
Semua logika machine learning dan evaluasi risiko sudah dimodularisasi dalam folder `src/`:

1. **`src/models.py`**:
   - `prediksi_lightgbm(y_latih, horizon_maks, kal)`: Menghasilkan ramalan titik $h=1..6$ bulan ke depan.
   - `ramal_sarimax_interval(y_latih, horizon_maks, kal, level)`: Menghasilkan ramalan titik dan confidence interval model parametrik SARIMAX.
   - `hitung_kuantil_konformal(residuals_df, level)`: Menghitung koreksi lebar pita Conformal Prediction.
2. **`src/risk.py`**:
   - `tentukan_status_risiko(nilai_batas_atas, ambang_kapasitas, batas_waspada)`: Mengembalikan string status (`"Aman"`, `"Waspada"`, `"Kritis"`).
   - `klasifikasi_tabel_risiko(df_prediksi, ambang_kapasitas, batas_waspada)`: Memetakan tabel prediksi menjadi okupansi kapasitas dan status risiko operasional.
   - `analisis_sensitivitas(df_prediksi, ambang_dasar)`: Menghitung matriks skenario jika kapasitas bergeser $\pm 5\%$ dan $\pm 10\%$.
3. **`src/config.py`**:
   - Berisi konstanta proyek: `AMBANG_KAPASITAS` (default: `34000.0` ribu), `BATAS_WASPADA` (`0.90`), `KOLOM_TARGET` (`penumpang_ribu`).

### B. Format Data Kontrak (Data Contract / JSON Schema)
Jika Back-End membungkus model ke dalam REST API (misal FastAPI/Flask), gunakan struktur payload berikut:

#### Endpoint: `GET /api/forecast/six-months`
**Response JSON:**
```json
{
  "model_digunakan": "LightGBM Multi-Horizon + Conformal Prediction",
  "ambang_kapasitas_ribu": 34000.0,
  "batas_waspada_rasio": 0.90,
  "data_prakiraan": [
    {
      "horizon": 1,
      "tanggal_target": "2026-09-01",
      "bulan_label": "Sep 2026",
      "prediksi_titik": 31304.6,
      "interval_80": {
        "batas_bawah": 29643.8,
        "batas_atas": 32965.5
      },
      "interval_95": {
        "batas_bawah": 29039.1,
        "batas_atas": 33570.1
      },
      "okupansi_batas_atas_persen": 98.7,
      "status_risiko": "Waspada"
    },
    {
      "horizon": 2,
      "tanggal_target": "2026-10-01",
      "bulan_label": "Okt 2026",
      "prediksi_titik": 31365.3,
      "interval_80": {
        "batas_bawah": 29743.5,
        "batas_atas": 32987.1
      },
      "interval_95": {
        "batas_bawah": 28347.4,
        "batas_atas": 34383.3
      },
      "okupansi_batas_atas_persen": 101.1,
      "status_risiko": "Kritis"
    }
  ]
}
```

### C. Alur Pembaruan Data Bulanan (Monthly Ingestion Flow)
Jika bulan depan BPS merilis data baru:
1. Masukkan baris baru ke `data/raw/` atau tambahkan ke `data/processed/data_final.csv`.
2. Jalankan fungsi `src/features.py` untuk menggeser horizon lag.
3. Model LightGBM akan otomatis melakukan inference 6 bulan ke depan dari titik origin baru tersebut.

---

## 3. Petunjuk Khusus untuk Pengembang Front-End

### A. Hierarki Tampilan UI yang Direkomendasikan
Dashboard telah dibangun dengan Streamlit di [`app/app.py`](file:///C:/Users/LENOVO/OneDrive/Documents/KULIAH%20COYYY/SEMESTER%205/Sistem%20Cerdas/prediksi-penumpang-krl-jabodetabek/app/app.py). Jika ingin mengembangkan atau memodifikasinya, pastikan mempertahankan 4 elemen kunci berikut:

#### 1. Panel Kontrol Interaktif (Sidebar)
- **Slider Ambang Kapasitas**: Rentang `28.000` s/d `40.000` (Step `500`, Default `34.000`).
  - *Behavior*: Saat slider digeser, seluruh status badge dan rasio okupansi di tabel/grafik harus langsung berubah secara reaktif (*reactive state*).
- **Selector Tingkat Keyakinan**: Pilihan radio antara `95% (Konservatif / Standar Peringatan Dini)` dan `80% (Moderat)`.
- **Selector Model**: Dropdown pilihan model `LightGBM (Multi-Horizon)` vs `SARIMAX`.

#### 2. Kartu Ringkasan (KPI Cards) di Bagian Atas
Tampilkan 4 metrik penting sebelum grafik:
- **Rata-rata Prediksi 6 Bulan**: Misal `31.139 ribu` (Okupansi rata-rata terhadap kapasitas).
- **Puncak Batas Atas (Peak Risk)**: Nilai tertinggi batas atas (misal `35.355 ribu`).
- **Ambang Kapasitas Aktif**: Menampilkan kapasitas yang sedang dipilih di slider.
- **Status Risiko Tertinggi**: Banner status global (`KRITIS 🚨`, `WASPADA ⚠️`, atau `AMAN ✅`).

#### 3. Grafik Interaktif Time Series
- **Sumbu X**: Waktu/Bulan (format: `Bulan Tahun`, misal `Jan 2025` s/d `Feb 2027`).
- **Sumbu Y**: Penumpang dalam satuan **Ribu Orang**.
- **Elemen Garis**:
  - Garis hitam solid: Data historis 24 bulan terakhir.
  - Garis putus-putus biru/hijau: Titik ramalan 6 bulan ke depan.
  - Area arsiran (Shaded Band): Rentang batas bawah s/d batas atas (alpha: 0.15 - 0.25).
  - Garis horizontal merah tebal: Ambang Kritis ($100\%$ kapasitas).
  - Garis horizontal oranye putus-putus: Batas Waspada ($90\%$ kapasitas).

#### 4. Pedoman Warna & Indikator Status (Design System)
Wajib menggunakan konsistensi warna peringatan standar berikut:

| Status Risiko | Definisi Kondisi | Kode Warna HEX | Rekomendasi Badge UI |
|---|---|:---:|---|
| **Aman** | Batas Atas $< 90\%$ Ambang Kapasitas | `#28a745` (Green) | `background: #e6ffec; color: #006622;` |
| **Waspada** | $90\% \le$ Batas Atas $< 100\%$ Ambang Kapasitas | `#ffc107` (Orange/Amber) | `background: #fff0cc; color: #996600;` |
| **Kritis** | Batas Atas $\ge 100\%$ Ambang Kapasitas | `#dc3545` (Red) | `background: #ffcccc; color: #990000; font-weight: bold;` |

---

## 4. Cara Menjalankan Aplikasi

```bash
# 1. Pastikan virtual environment aktif
# Windows:
venv\Scripts\activate

# 2. Jalankan dashboard Streamlit
cd prediksi-penumpang-krl-jabodetabek
streamlit run app/app.py
```

Dashboard akan otomatis terbuka pada browser di alamat:  
`http://localhost:8501`

---

## 5. Pertanyaan Umum (FAQ) untuk Dev Team

1. **T: Mengapa target peramalan berupa interval, bukan hanya 1 angka?**  
   *J:* Di transportasi publik, ramalan 1 angka tidak bisa mengantisipasi lonjakan jam sibuk. Dengan interval prediksi (terutama batas atas 95%), operator memiliki jaminan batas maksimal penumpang sehingga mitigasi overcapacity bisa disiapkan sebelum krisis terjadi.

2. **T: Dari mana angka ambang 34.000 ribu diperoleh?**  
   *J:* Angka 34 juta penumpang/bulan setara dengan rata-rata ~1,1 juta penumpang per hari kerja, yang merupakan batas okupansi teknis armada KRL Jabodetabek saat ini. Angka ini fleksibel dan dapat diatur lewat slider di dashboard atau di `src/config.py`.

3. **T: Apakah grafik sudah siap untuk presentasi slide?**  
   *J:* Ya, seluruh grafik resolusi tinggi (150 DPI) sudah otomatis tersimpan di folder `reports/figures/` dan siap disalin ke slide PowerPoint.
