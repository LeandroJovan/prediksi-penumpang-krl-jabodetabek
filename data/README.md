# Dokumentasi Data

Proyek: Prediksi Permintaan Penumpang KRL Jabodetabek Berbasis Time Series
dengan Interval Prediksi (Batas Atas dan Bawah)

## 1. Struktur Folder Data

```
data/
├── raw/         # data mentah (JANGAN diedit)
├── processed/   # data hasil pembersihan dan penggabungan
└── README.md    # dokumen ini
```

## 2. Isi Folder `raw/`

| File | Isi | Jumlah |
|---|---|---|
| `Jumlah_Penumpang_Kereta_Api__<tahun>.csv` | Tabel bulanan penumpang kereta api per kategori, satu file per tahun (2016–2026) | 11 file |
| `kalender_eksogen_krl_2013_2026.csv` | Kalender: hari kerja, libur nasional, penanda Lebaran, penanda COVID | 1 file |

> Catatan: isi nomor jumlah file sesuai file yang benar-benar ada di folder `raw/`.

## 3. Sumber Data

| Data | Sumber | Keterangan |
|---|---|---|
| Jumlah penumpang kereta api | Badan Pusat Statistik (BPS), tabel "Jumlah Penumpang Kereta Api" | Sumber asli BPS: PT KAI dan KAI Commuter |
| Kalender eksogen | Dibangkitkan dengan library Python `holidays` | Hari kerja dihitung sebagai Senin–Jumat dikurangi libur nasional |

- Tanggal akses / unduh data BPS: **[isi tanggal]**
- Tautan tabel BPS: https://www.bps.go.id/id/statistics-table/2/NzIjMg==/jumlah-penumpang-kereta-api.html
- Versi library `holidays` yang dipakai: **[isi versi]**

## 4. Satuan dan Cakupan

- **Satuan penumpang: RIBU ORANG** (contoh: 26733 berarti 26,733 juta penumpang).
- Granularitas: bulanan.
- Cakupan: hanya kategori **Jabodetabek** (baris lain seperti Non Jabodetabek,
  Kereta Bandara, MRT, LRT, dan Whoosh tidak dipakai).
- Rentang waktu: Januari 2016 sampai bulan terakhir yang sudah dirilis BPS.
- Tanda `-` pada data BPS berarti kosong / belum tersedia.

## 5. Format File Mentah BPS

Tiap file berformat "lebar" (wide):

- 3 baris pertama adalah judul dan tahun.
- Baris ke-4 adalah header bulan (Januari sampai Desember, lalu Tahunan).
- Baris berikutnya adalah kategori (Jabodetabek, Non Jabodetabek, dst).

Kolom `Tahunan` tidak dipakai sebagai data, tetapi dipakai sebagai alat validasi
(jumlah 12 bulan harus sama dengan nilai Tahunan).

## 6. Kamus Data Hasil Olahan (`processed/data_final.csv`)

| Kolom | Tipe | Keterangan |
|---|---|---|
| `year_month` | teks | Periode, format `YYYY-MM` |
| `tanggal` | tanggal | Tanggal 1 tiap bulan |
| `penumpang_ribu` | angka | **Variabel target.** Jumlah penumpang KRL Jabodetabek (ribu orang) |
| `total_hari` | integer | Jumlah hari dalam bulan |
| `jumlah_hari_kerja` | integer | Jumlah hari kerja (Senin–Jumat, di luar libur nasional) |
| `jumlah_libur_nasional_weekday` | integer | Jumlah libur nasional yang jatuh pada hari kerja |
| `is_lebaran` | 0/1 | 1 jika bulan tersebut adalah bulan Idul Fitri |
| `is_covid` | 0/1 | 1 untuk periode Maret 2020 sampai Desember 2022 |

File lain di `processed/`:

- `kalender_future.csv`: kalender bulan yang belum punya data aktual (dipakai saat meramal).
- `validasi_tahunan.csv`: hasil pengecekan jumlah 12 bulan vs kolom Tahunan.

## 7. Catatan Kualitas Data

1. Kolom `is_covid_mar20_dec22` pada file kalender bertipe teks dan ada 1 nilai
   rusak (`` 0` ``). Nilai ini dibersihkan menjadi 0.
2. File kalender punya 2 penanda COVID. Yang dipakai adalah `is_covid_mar20_dec22`
   (mulai Maret 2020), karena Januari–Februari 2020 masih normal.
   Kolom `is_covid_2020_2022` dibuang.
3. Data kalender 2013–2015 dihapus (data target mulai 2016).
4. Angka BPS dan angka KAI berbeda untuk tahun yang sama. Proyek ini hanya
   memakai **satu sumber (BPS)** sebagai seri utama.
5. Penumpang tercatat belum tentu sama dengan permintaan sebenarnya
   (kemungkinan tertahan kapasitas).
6. `is_lebaran` hanya menandai bulan Idul Fitri; efek mudik di bulan sebelum
   dan sesudahnya dibuat sebagai fitur tambahan di tahap feature engineering.

## 8. Log Perubahan

| Tanggal | Perubahan |
|---|---|
| [isi tanggal] | Data mentah diunduh dan disimpan di `raw/` |
| [isi tanggal] | 11 file BPS digabung menjadi `data_final.csv` |

## 9. Cara Mereproduksi

1. Letakkan semua file mentah di `data/raw/`.
2. Jalankan `notebooks/01_data_prep.ipynb` dari atas sampai bawah.
3. Hasil tersimpan di `data/processed/`.