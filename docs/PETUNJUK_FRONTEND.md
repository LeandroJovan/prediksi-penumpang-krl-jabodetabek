# 🎨 Petunjuk Teknis untuk Tim Front-End
## Proyek Sistem Cerdas: Prediksi Permintaan Penumpang KRL Jabodetabek

Dokumen ini disusun khusus sebagai panduan desain dan antarmuka bagi pengembang **Front-End** dalam menyajikan visualisasi time series, kartu metrik (KPI), kontrol interaktif pengguna, dan sistem warna peringatan risiko kapasitas KRL.

---

## 1. Tanggung Jawab Tim Front-End
1. Menyajikan dashboard interaktif yang mudah dipahami oleh dosen, operator KRL (PT KAI Commuter), dan pengambil kebijakan (DJKA Kemenhub).
2. Memfasilitasi interaksi pengguna (slider ambang kapasitas, pemilihan tingkat interval 80% vs 95%).
3. Menerjemahkan angka probabilitas batas atas menjadi sistem peringatan visual yang jelas (**Aman**, **Waspada**, **Kritis**).

---

## 2. Struktur Direktori Terkait Front-End

```
prediksi-penumpang-krl-jabodetabek/
├── app/
│   └── app.py                     # Dashboard interaktif Streamlit
├── reports/figures/               # Grafik resolusi tinggi siap pakai
│   ├── lgbm_01_mase_per_horizon.png
│   ├── lgbm_02_prediksi_vs_aktual.png
│   ├── lgbm_03_conformal_interval.png
│   ├── lgbm_04_feature_importance.png
│   └── risiko_01_kapasitas_alert.png
└── outputs/                       # File CSV siap konsumsi oleh UI
    ├── prediksi_future_6bln.csv
    ├── metrik_komparasi_final.csv
    └── analisis_sensitivitas_kapasitas.csv
```

---

## 3. Menjalankan Dashboard Bawaan (Streamlit)

Aplikasi dashboard web berbasis Streamlit sudah siap dijalankan di laptop lokal:

```bash
cd prediksi-penumpang-krl-jabodetabek
streamlit run app/app.py
```
Aplikasi akan terbuka otomatis di browser pada URL: `http://localhost:8501`.

---

## 4. Spesifikasi Komponen Tampilan (UI Component Specs)

### A. Kontrol Sidebar (User Inputs)
Front-End harus menyediakan kontrol berikut:
1. **Slider Ambang Kapasitas**:
   - Rentang: `28.000` s/d `40.000` ribu orang/bulan (Langkah: `500`).
   - Default: `34.000` ribu (setara kapasitas teknis saat ini).
   - *Behavior*: Saat nilai slider digeser, semua status badge dan grafik harus langsung diperbarui (*reactive update*).
2. **Pilihan Interval Prediksi**:
   - Radio button:
     - `95% (Konservatif / Standar Peringatan Risiko)` -> Menggunakan kolom `batas_atas_95`.
     - `80% (Moderat)` -> Menggunakan kolom `batas_atas_80`.
3. **Pilihan Model**:
   - Dropdown antara `LightGBM (Multi-Horizon)` dan `SARIMAX`.

### B. Kartu Ringkasan Atas (KPI Cards)
Tampilkan 4 kartu ringkasan di bagian atas dashboard:
1. **Rata-rata Prediksi 6 Bulan**: Menampilkan rata-rata titik permintaan (misal `31.139 ribu`).
2. **Puncak Batas Atas**: Menampilkan nilai tertinggi dari batas atas interval (misal `35.355 ribu`).
3. **Ambang Kapasitas Aktif**: Menampilkan nilai slider kapasitas saat ini.
4. **Status Risiko Global**: Badge warna besar status terburuk dari 6 bulan ke depan (`KRITIS 🚨`, `WASPADA ⚠️`, atau `AMAN ✅`).

### C. Grafik Time Series dengan Pita Ketidakpastian
Grafik peramalan harus memuat 4 lapisan:
1. **Garis Historis Aktual**: Menampilkan data aktual 24 bulan ke belakang (garis solid hitam).
2. **Garis Prakiraan Titik**: Menampilkan hasil ramalan 6 bulan ke depan (garis putus-putus biru/hijau dengan titik lingkaran).
3. **Pita Ketidakpastian (Shaded Area)**: Area arsiran transparan (opacity 15%–25%) antara batas bawah dan batas atas.
4. **Garis Batas Kapasitas**:
   - Garis horizontal merah solid pada level ambang kapasitas ($100\%$).
   - Garis horizontal oranye putus-putus pada level batas waspada ($90\%$).

---

## 5. Sistem Warna & Badge Status Risiko (Design System)

Wajib menggunakan palet warna standar berikut pada kartu, tabel, dan grafik:

| Status | Logika Kondisi | Warna HEX | Background CSS | Keterangan untuk Pengguna |
|:---:|---|:---:|---|---|
| **Aman** | Batas atas $< 90\%$ kapasitas | `#28a745` | `#e6ffec` (Teks: `#006622`) | Beban penumpang aman, kapasitas mencukupi. |
| **Waspada** | $90\% \le$ Batas atas $< 100\%$ | `#ffc107` | `#fff0cc` (Teks: `#996600`) | Potensi kepadatan tinggi pada jam sibuk. |
| **Kritis** | Batas atas $\ge 100\%$ kapasitas | `#dc3545` | `#ffcccc` (Teks: `#990000`) | Risiko overcapacity dan penumpukan peron. |

---

## 6. Opsi Integrasi: Mode CSV vs Mode REST API

Front-End dapat beroperasi dengan dua cara:

1. **Mode Mandiri (Direct CSV)**:
   - Front-End membaca langsung file di folder `outputs/prediksi_future_6bln.csv` menggunakan pandas / d3.js / papaparse.
   - Perhitungan status risiko dilakukan menggunakan fungsi di `src/risk.py` (sudah diimplementasikan di `app/app.py`).

2. **Mode Terhubung ke Back-End API**:
   - Front-End mengirim request ke server backend Flask (`backend/api.py`):
     - `GET http://localhost:5000/api/forecast`
     - `POST http://localhost:5000/api/simulate-risk` (payload: `{ "ambang_kapasitas": 34000, "batas_waspada": 0.90 }`).
