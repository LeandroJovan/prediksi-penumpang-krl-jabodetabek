# Arsitektur Chatbot KRL Insight

Status: **diimplementasikan** (backend `POST /api/v1/chat`, frontend halaman *Asisten AI*).

## Prinsip

1. **Berbasis fakta.** Setiap angka berasal dari prakiraan, perhitungan risiko, atau statistik riwayat yang
   dihitung dari `data/processed/data_final.csv`. Tidak ada angka atau klaim domain yang ditulis tangan
   (versi lama frontend menulis "Lebaran selalu turun 15–25%" dan "korelasi hari kerja > 0,85"; data sebenarnya
   −7,3% rata-rata dan 0,29).
2. **Aturan dulu, LLM belakangan.** Pertanyaan terstruktur dijawab deterministik (cepat, murah, tidak bisa
   berhalusinasi). LLM hanya dipakai untuk pertanyaan bebas (`intent = general`).
3. **LLM tidak dipercaya.** Keluarannya divalidasi: skema JSON ketat, panjang, tanpa tautan/HTML, dan setiap
   angka harus ada di fakta. Gagal validasi atau Ollama mati → jawaban aturan.
4. **Server tidak mengirim HTML.** Klien menampilkan teks yang di-escape.

## Kontrak API

`POST /api/v1/chat` (dibatasi laju per IP, `RATE_LIMIT_PER_MINUTE`)

```jsonc
// Request
{
  "message": "Bagaimana jika kapasitas dinaikkan 10%?",   // 1..500 karakter, karakter kontrol dibuang
  "history": [{ "role": "user|assistant", "content": "…" }],  // maks 6 giliran; hanya dipakai jalur LLM
  "ambang_kapasitas": 34000                                  // opsional, ribu penumpang/bulan, 0 < x <= 1.000.000
}

// Response 200
{
  "data": {
    "intent": "scenario",
    "answer": "Dengan kapasitas naik 10% (34,0 menjadi 37,4 juta): 1 bulan Kritis, …",
    "bullets": ["Oktober 2026: Kritis (103,1%) menjadi Waspada (93,7%)."],
    "status": "kritis",                       // aman | waspada | kritis | belum_ditentukan | null
    "source": "rules",                        // rules | ollama
    "suggestions": ["Bagaimana jika kapasitas diturunkan 5%?"]
  },
  "meta": { "intent": "scenario", "forecast_model_run_id": "lgbm_cqr_v1",
            "data_through": "2026-08-01", "capacity_ribu": 34000.0, "model": null }
}
```

Kesalahan: `422` (payload tidak valid, field asing ditolak), `429` (laju), `503` (data prakiraan tidak tersedia).

## Intent

| Intent | Pemicu contoh | Sumber jawaban |
|---|---|---|
| `summary` | "Ringkasan proyeksi 6 bulan" | Ringkasan insight (satu sumber dengan panel insight) + baris per bulan |
| `risk` | "Analisis risiko kapasitas", "kenapa kritis?" | Kesimpulan dan poin insight |
| `recommend` | "Apa rekomendasi?" | Aksi dari insight sesuai status risiko |
| `month` | "Prediksi bulan Desember" | Baris prakiraan bulan itu; di luar horizon dijelaskan |
| `scenario` | "Bagaimana jika kapasitas naik 10%?", "kapasitas 36 juta" | `calculate_risk` dengan kapasitas baru, dibandingkan kondisi semula |
| `capacity` | "Berapa kapasitas saat ini?" | Kapasitas dan ambang Aman/Waspada/Kritis |
| `seasonal` | "Pola Lebaran dan hari kerja" | `chat_stats.history_stats` (dihitung dari data) |
| `interval` | "Apa itu skenario cukup padat?" | Penjelasan + cakupan backtest nyata (PICP) |
| `general` | pertanyaan bebas | Ollama (bila `CHAT_USE_LLM=true`), jika gagal → ringkasan aturan |

Catatan penafsiran skenario: angka tanpa satuan `kapasitas 36` dianggap juta; persentase harus `0 < x <= 100`.

## Keamanan

- Input: skema ketat (`extra="forbid"`), batas panjang, karakter kontrol dibuang, kapasitas dibatasi.
- Prompt injection: teks pengguna hanya masuk sebagai pesan `user` (tidak pernah digabung ke `system`);
  sistem tidak memiliki *tool* atau akses data selain fakta yang disuntikkan; keluaran divalidasi.
- XSS: server hanya mengirim teks polos; `frontend/js/chat.js` melakukan `escapeHtml` untuk semua teks
  (termasuk atribut `data-q` pada saran) dan hanya menerima status dari daftar putih.
- Beban: rate limit per IP; panggilan LLM dibatasi `OLLAMA_MAX_CONCURRENCY` dan `OLLAMA_TIMEOUT_SECONDS`.

## Konfigurasi

| Variabel | Default | Fungsi |
|---|---|---|
| `CHAT_USE_LLM` | `true` | `false` = hanya jawaban aturan (tanpa Ollama) |
| `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `OLLAMA_TIMEOUT_SECONDS`, `OLLAMA_MAX_CONCURRENCY` | lihat `.env.example` | Parameter LLM |
| `RATE_LIMIT_PER_MINUTE` | `120` | Batas laju per IP |

## Frontend

`frontend/js/chat.js` (modul murni, diuji `node --test`): `askChat` (POST + timeout), `renderAnswer`,
`escapeHtml`, `offlineAnswer`. Jika server tidak terjangkau (halaman dibuka lewat server statis/Flask, atau
mode demo), jawaban offline memakai `KRLInsight.buildInsight(data.json)` dan menyebut keterbatasannya; pertanyaan
yang butuh data riwayat diarahkan untuk menjalankan backend FastAPI.

## Batasan yang diketahui

- Bahasa jawaban hanya Indonesia. Fallback insight sudah dwibahasa, chat belum.
- Riwayat percakapan hanya dipakai jalur LLM; jawaban aturan tidak bergantung pada konteks sebelumnya.
- Pemahaman pertanyaan berbasis kata kunci; kalimat yang sangat bebas jatuh ke `general`.
- Cakupan interval (PICP) diambil dari backtest keseluruhan dan sama untuk semua subset.
