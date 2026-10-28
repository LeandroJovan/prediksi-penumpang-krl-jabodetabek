# KRL Insight Dashboard (Frontend Web)

Antarmuka web interaktif untuk pemantauan prediksi jumlah penumpang KRL Jabodetabek, visualisasi ketidakpastian (*prediction interval* 80% & 95%), evaluasi backtesting model, dan sistem peringatan dini risiko kapasitas operasional.

---

## 📁 Struktur Direktori Frontend

Mengikuti standar repositori GitHub untuk web static / client-side app:

```text
frontend/
├── index.html          # Entry point utama halaman web (SPA dengan routing hash)
├── css/
│   └── styles.css      # Desain tema, tipografi Inter, layout responsif & styling komponen
├── js/
│   └── app.js          # Router, chart logic (Chart.js), dan rule engine risiko
├── data/
│   └── data.json       # Data agregat dari pipeline model Python
└── README.md           # Dokumentasi teknis & panduan frontend
```

---

## 🚀 Cara Menjalankan Frontend

Karena dashboard memuat data secara dinamis dari `data/data.json` menggunakan `fetch()`, aplikasi perlu dijalankan melalui web server lokal (bukan double-click `file://` agar tidak terhambat aturan CORS browser).

### Opsi 1: Menggunakan Python Built-in HTTP Server (Rekomendasi)
Buka terminal dari root repository, masuk ke folder `frontend/`, dan jalankan:

```bash
cd frontend
python -m http.server 8000
```
Buka browser dan akses: `http://localhost:8000`

### Opsi 2: Menggunakan VS Code / Cursor / Antigravity IDE (Live Server)
1. Pasang ekstensi **Live Server**.
2. Klik kanan pada file `frontend/index.html` -> pilih **Open with Live Server**.

---

## 🔗 Hubungan dengan Pipeline Tim (Machine Learning & Data Prep)

Dashboard ini terhubung langsung dengan hasil data preparation dan backtesting tim data science melalui file `frontend/data/data.json`.

Jika tim memperbarui data mentah BPS atau melatih model baru (misalnya SARIMAX atau LightGBM), jalankan perintah berikut dari root repositori:

```bash
python src/export_app_data.py
```

Script tersebut akan secara otomatis:
1. Membaca data historis terbaru dari `data/processed/data_final.csv`.
2. Menghasilkan ramalan titik (*point forecast*) 6 bulan ke depan.
3. Mengkalibrasi *Prediction Interval* (80% dan 95%) menggunakan *conformal residual calibration*.
4. Mengisi metrik backtesting (MASE, RMSE, MAE, PICP, MPIW, Winkler) ke `frontend/data/data.json`.
5. Menampilkan status data terhubung di dashboard.

---

## 🧭 Halaman & Fitur Dashboard

1. **Beranda (`#beranda`)**: Landing page sederhana untuk langsung masuk ke Dashboard KRL Insight.
2. **Dashboard Utama (`#dashboard`)**: Ringkasan eksekutif, status risiko kapasitas (Aman/Waspada/Kritis), grafik tren dan batas atas 95%.
3. **Prediksi Penumpang (`#prediksi`)**: Proyeksi 1–6 bulan dengan rentang ketidakpastian 80% & 95%, serta fitur ekspor CSV.
4. **Analisis Historis (`#historis`)**: Eksplorasi deret waktu 2016–2026, dekomposisi tahunan, pola musiman, dampak Lebaran & COVID-19.
5. **Risiko Kapasitas (`#risiko`)**: Komparasi batas atas 95% terhadap ambang kapasitas dengan simulasi sensitivitas ($\pm 5\%$, $\pm 10\%$).
6. **Evaluasi Model (`#evaluasi`)**: Metrik ilmiah komparatif (MASE, PICP, MPIW) seluruh periode vs pasca-COVID tanpa kebocoran data.
