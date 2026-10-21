# Dataset Metadata - Prediksi Penumpang KRL Jabodetabek

Dokumentasi mengenai sumber, struktur, dan keterangan data yang digunakan dalam proyek ini.

---

## 1. Sumber Data
- **Penyedia Data:** Badan Pusat Statistik (BPS) / Open Data Kemenhub / PT KAI Commuter
- **Nama Publikasi / Tabel:** Jumlah Penumpang Kereta Api (Komuter Jabodetabek)
- **Tautan Sumber:** *(Isi tautan resmi BPS / portal data terbuka)*
- **Tanggal Akses / Pengambilan Data:** 2026-10-21

---

## 2. Struktur Folder
- `data/raw/`: Berisi file dataset mentah persis seperti saat diunduh (format `.csv`, `.xlsx`). **Jangan diedit secara manual.**
- `data/processed/`: Berisi data hasil pembersihan (*cleaning*), penanganan *missing values*, agregasi waktu, dan *feature engineering*.

---

## 3. Metadata & Keterangan Variabel
| Nama Kolom / Fitur | Tipe Data | Satuan / Format | Keterangan |
|---|---|---|---|
| `periode` / `tanggal` | Date | `YYYY-MM` / `YYYY-MM-DD` | Periode pencatatan data |
| `jumlah_penumpang` | Numeric | Ribu Orang / Orang | Total volume penumpang KRL Jabodetabek |
| `...` | ... | ... | ... |

---

## 4. Catatan Khusus
- Perhatikan anomali data pada periode khusus (misalnya masa pandemi COVID-19 tahun 2020 - 2022).
- Pastikan satuan data konsisten (misal: jika BPS menggunakan satuan *Ribu Penumpang*, tentukan apakah akan distandarisasi ke satuan orang utuh atau tetap ribuan).
