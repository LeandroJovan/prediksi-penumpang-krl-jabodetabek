"""
data_prep.py
------------
Modul untuk membaca, menggabungkan, dan membersihkan data:
1. Data jumlah penumpang kereta api (BPS) -> ambil baris Jabodetabek saja
2. Data kalender eksogen (hasil library holidays)

Cara kerja singkat:
- File BPS formatnya "lebar" (bulan = kolom), jadi diubah ke format "panjang"
  (1 baris = 1 bulan).
- Kolom "Tahunan" dipakai untuk validasi hasil parsing.
"""

import os
import re
import glob
import numpy as np
import pandas as pd

# ---------------------------------------------------------------
# Konstanta
# ---------------------------------------------------------------
NAMA_BULAN = ["januari", "februari", "maret", "april", "mei", "juni",
              "juli", "agustus", "september", "oktober", "november", "desember"]

# label baris yang dianggap Jabodetabek (harus SAMA PERSIS,
# supaya "Non Jabodetabek (Jawa)" tidak ikut terambil)
LABEL_JABODETABEK = ["jabodetabek", "jabotabek"]

TAHUN_MULAI = 2016

# batas nilai wajar (satuan ribu orang), untuk mendeteksi salah baca
BATAS_BAWAH_WAJAR = 1000
BATAS_ATAS_WAJAR = 60000


# ---------------------------------------------------------------
# BAGIAN 1: DATA PENUMPANG (BPS)
# ---------------------------------------------------------------
def ke_angka(nilai):
    """Ubah teks dari CSV BPS menjadi angka. Tanda '-' dan kosong jadi NaN."""
    if pd.isna(nilai):
        return np.nan

    teks = str(nilai).strip()

    if teks in ["", "-", "–", "nan", "NaN", "..."]:
        return np.nan

    # kasus "26733.0" -> buang ".0" dulu supaya tidak dianggap pemisah ribuan
    if re.fullmatch(r"\d+\.0+", teks):
        teks = teks.split(".")[0]

    # buang pemisah ribuan (titik, koma, spasi)
    teks = teks.replace(".", "").replace(",", "").replace(" ", "")

    try:
        return float(teks)
    except ValueError:
        return np.nan


def cari_baris_header(raw):
    """Cari baris yang berisi nama-nama bulan (Januari, Februari, ...)."""
    for i in range(len(raw)):
        jumlah_cocok = 0
        for sel in raw.iloc[i]:
            if pd.notna(sel) and str(sel).strip().lower() in NAMA_BULAN:
                jumlah_cocok += 1
        if jumlah_cocok >= 6:   # minimal 6 nama bulan -> pasti baris header
            return i
    raise ValueError("Baris header bulan tidak ditemukan di file ini.")


def cari_tahun(raw, baris_header):
    """Cari angka tahun (contoh 2020) di baris-baris SEBELUM header bulan."""
    for i in range(baris_header):
        for sel in raw.iloc[i]:
            if pd.notna(sel) and re.fullmatch(r"\s*20\d{2}\s*", str(sel)):
                return int(str(sel).strip())
    raise ValueError("Tahun tidak ditemukan di baris judul file ini.")


def baca_satu_file(path_file):
    """
    Baca 1 file BPS, ambil baris Jabodetabek.
    Hasil: dictionary berisi tahun, tabel 12 bulan, dan nilai Tahunan resmi.
    """
    # semua sel dibaca sebagai teks dulu (dtype=str) supaya tidak salah tebak tipe.
    # utf-8-sig dipakai karena file BPS ada karakter BOM di awal.
    raw = pd.read_csv(path_file, header=None, dtype=str,
                      encoding="utf-8-sig", names=list(range(20)))

    # 1. cari posisi header bulan dan tahun
    baris_header = cari_baris_header(raw)
    tahun = cari_tahun(raw, baris_header)

    # cek silang dengan tahun di nama file
    tahun_di_nama = re.findall(r"(20\d{2})", os.path.basename(path_file))
    if len(tahun_di_nama) > 0 and int(tahun_di_nama[-1]) != tahun:
        print(f"  PERINGATAN: tahun di nama file ({tahun_di_nama[-1]}) "
              f"beda dengan tahun di isi file ({tahun}). Dipakai: {tahun}")

    # 2. petakan nomor bulan -> nomor kolom
    kolom_bulan = {}
    kolom_tahunan = None
    for j in range(raw.shape[1]):
        sel = raw.iloc[baris_header, j]
        if pd.isna(sel):
            continue
        teks = str(sel).strip().lower()
        if teks in NAMA_BULAN:
            kolom_bulan[NAMA_BULAN.index(teks) + 1] = j
        elif teks in ["tahunan", "jumlah", "total"]:
            kolom_tahunan = j

    if len(kolom_bulan) != 12:
        raise ValueError(f"Kolom bulan yang ditemukan hanya {len(kolom_bulan)}, harusnya 12.")

    # 3. cari baris Jabodetabek (label harus sama persis)
    baris_jabo = None
    daftar_label = []
    for i in range(baris_header + 1, len(raw)):
        label = str(raw.iloc[i, 0]).strip().lower()
        daftar_label.append(label)
        if label in LABEL_JABODETABEK:
            baris_jabo = i
            break

    if baris_jabo is None:
        raise ValueError(f"Baris Jabodetabek tidak ketemu. Label yang ada: {daftar_label}")

    # 4. ambil 12 nilai bulanan
    daftar = []
    for bulan in range(1, 13):
        kolom = kolom_bulan[bulan]
        nilai = ke_angka(raw.iloc[baris_jabo, kolom])
        daftar.append({
            "year_month": f"{tahun}-{bulan:02d}",
            "penumpang_ribu": nilai
        })
    tabel = pd.DataFrame(daftar)

    # 5. ambil nilai Tahunan resmi (untuk validasi)
    tahunan_resmi = np.nan
    if kolom_tahunan is not None:
        tahunan_resmi = ke_angka(raw.iloc[baris_jabo, kolom_tahunan])

    # 6. cek nilai wajar
    for _, baris in tabel.iterrows():
        v = baris["penumpang_ribu"]
        if pd.notna(v) and (v < BATAS_BAWAH_WAJAR or v > BATAS_ATAS_WAJAR):
            print(f"  PERINGATAN: nilai tidak wajar di {baris['year_month']}: {v}")

    return {"tahun": tahun, "tabel": tabel, "tahunan_resmi": tahunan_resmi}


def gabung_semua(folder_raw, pola="Jumlah Penumpang Kereta Api*.csv"):
    """
    Baca semua file BPS di folder_raw lalu gabungkan.
    Hasil: (tabel target, tabel validasi tahunan)
    """
    daftar_file = sorted(glob.glob(os.path.join(folder_raw, pola)))
    if len(daftar_file) == 0:
        raise FileNotFoundError(f"Tidak ada file dengan pola '{pola}' di {folder_raw}")

    print(f"Ditemukan {len(daftar_file)} file.")

    semua_tabel = []
    baris_validasi = []
    tahun_sudah_ada = []

    for path_file in daftar_file:
        nama = os.path.basename(path_file)
        print(f"Membaca: {nama}")
        hasil = baca_satu_file(path_file)
        tahun = hasil["tahun"]

        # cegah tahun yang sama terbaca dua kali (misal file salinan)
        if tahun in tahun_sudah_ada:
            raise ValueError(f"Tahun {tahun} terbaca lebih dari sekali. Cek file duplikat.")
        tahun_sudah_ada.append(tahun)

        tabel = hasil["tabel"]
        semua_tabel.append(tabel)

        # siapkan data validasi: jumlah 12 bulan vs kolom Tahunan
        jumlah_terisi = int(tabel["penumpang_ribu"].notna().sum())
        jumlah_12_bulan = tabel["penumpang_ribu"].sum()   # NaN dilewati
        tahunan_resmi = hasil["tahunan_resmi"]

        if jumlah_terisi < 12:
            status = "Tidak lengkap (tahun berjalan / ada bulan kosong)"
            selisih = np.nan
        elif pd.isna(tahunan_resmi):
            status = "Kolom Tahunan tidak ada"
            selisih = np.nan
        else:
            selisih = jumlah_12_bulan - tahunan_resmi
            status = "OK" if abs(selisih) <= 10 else "BEDA, CEK PARSING"

        baris_validasi.append({
            "tahun": tahun,
            "file": nama,
            "bulan_terisi": jumlah_terisi,
            "jumlah_12_bulan": jumlah_12_bulan,
            "tahunan_resmi": tahunan_resmi,
            "selisih": selisih,
            "status": status
        })

    target = pd.concat(semua_tabel, ignore_index=True)
    target = target.sort_values("year_month").reset_index(drop=True)
    tabel_validasi = pd.DataFrame(baris_validasi).sort_values("tahun").reset_index(drop=True)

    return target, tabel_validasi


def potong_bulan_belum_rilis(target):
    """
    Buang bulan-bulan kosong di UJUNG deret (bulan yang belum dirilis BPS).
    Bulan kosong di TENGAH deret tidak dibuang (ditangani terpisah).
    """
    ada_isi = target[target["penumpang_ribu"].notna()]
    bulan_terakhir = ada_isi["year_month"].max()
    hasil = target[target["year_month"] <= bulan_terakhir].copy()
    return hasil.reset_index(drop=True), bulan_terakhir


def cari_data_hilang(target):
    """Daftar bulan yang nilainya kosong (NaN)."""
    return target.loc[target["penumpang_ribu"].isna(), "year_month"].tolist()


def tangani_data_hilang(target, metode="interpolasi"):
    """
    Tangani NaN di tengah deret.
    Kolom is_imputed menandai baris mana yang hasil isian (bukan data asli).
    """
    hasil = target.copy()
    hasil["is_imputed"] = hasil["penumpang_ribu"].isna().astype(int)

    if metode == "interpolasi":
        hasil["penumpang_ribu"] = hasil["penumpang_ribu"].interpolate(method="linear")
    elif metode == "hapus":
        hasil = hasil.dropna(subset=["penumpang_ribu"]).reset_index(drop=True)
    else:
        raise ValueError("metode harus 'interpolasi' atau 'hapus'")
    return hasil


# ---------------------------------------------------------------
# BAGIAN 2: DATA KALENDER EKSOGEN
# ---------------------------------------------------------------
def bersihkan_kalender(path_kalender):
    """Baca, bersihkan, dan filter kalender (mulai TAHUN_MULAI)."""
    kal = pd.read_csv(path_kalender, dtype=str, encoding="utf-8-sig")
    kal.columns = [k.strip() for k in kal.columns]

    kolom_angka = ["total_hari", "jumlah_hari_kerja", "jumlah_libur_nasional_weekday",
                   "is_lebaran", "is_covid_2020_2022", "is_covid_mar20_dec22"]

    # Ambil hanya digit dari tiap sel. Contoh "0`" menjadi "0".
    for kolom in kolom_angka:
        asli = kal[kolom].str.strip()
        bersih = asli.str.extract(r"(\d+)")[0]
        jumlah_rusak = int((asli != bersih).sum())
        if jumlah_rusak > 0:
            print(f"Kolom {kolom}: {jumlah_rusak} sel diperbaiki")
        kal[kolom] = bersih.astype(int)

    kal["year_month"] = kal["year_month"].str.strip()

    # pilih penanda COVID yang mulai Maret 2020, buang yang lain
    kal = kal.rename(columns={"is_covid_mar20_dec22": "is_covid"})
    kal = kal.drop(columns=["is_covid_2020_2022", "tanggal"])

    # buang data sebelum TAHUN_MULAI
    kal = kal[kal["year_month"] >= f"{TAHUN_MULAI}-01"].reset_index(drop=True)

    # ---- pengecekan kualitas ----
    assert kal["year_month"].is_unique, "Ada year_month duplikat di kalender"
    assert (kal["jumlah_hari_kerja"] <= kal["total_hari"]).all(), "Hari kerja melebihi total hari"
    assert kal["is_lebaran"].isin([0, 1]).all(), "is_lebaran harus 0/1"
    assert kal["is_covid"].isin([0, 1]).all(), "is_covid harus 0/1"

    # cek urutan bulan tidak ada yang loncat
    rentang = pd.date_range(kal["year_month"].iloc[0] + "-01",
                            kal["year_month"].iloc[-1] + "-01", freq="MS")
    assert len(rentang) == len(kal), "Ada bulan yang loncat di kalender"

    return kal


# ---------------------------------------------------------------
# BAGIAN 3: PENGGABUNGAN TARGET + KALENDER
# ---------------------------------------------------------------
def gabung_target_kalender(target, kalender):
    """
    Gabungkan target dan kalender (left join dari target).
    Hasil: (data_final, kalender_future)
    kalender_future = bulan-bulan yang belum punya data aktual (untuk meramal).
    """
    data = pd.merge(target, kalender, on="year_month", how="left")

    # kalau ada kalender yang tidak ketemu -> berarti ada bulan yang tidak cocok
    if data["jumlah_hari_kerja"].isna().any():
        bulan_bermasalah = data.loc[data["jumlah_hari_kerja"].isna(), "year_month"].tolist()
        raise ValueError(f"Kalender tidak ditemukan untuk: {bulan_bermasalah}")

    # kolom angka kalender dikembalikan ke integer
    for kolom in ["total_hari", "jumlah_hari_kerja", "jumlah_libur_nasional_weekday",
                  "is_lebaran", "is_covid"]:
        data[kolom] = data[kolom].astype(int)

    data["tanggal"] = pd.to_datetime(data["year_month"] + "-01")

    # susun urutan kolom
    urutan = ["year_month", "tanggal", "penumpang_ribu", "total_hari",
              "jumlah_hari_kerja", "jumlah_libur_nasional_weekday",
              "is_lebaran", "is_covid"]
    if "is_imputed" in data.columns:
        urutan.append("is_imputed")
    data = data[urutan]

    # kalender masa depan = bulan setelah data aktual terakhir
    bulan_terakhir = target["year_month"].max()
    kalender_future = kalender[kalender["year_month"] > bulan_terakhir].copy()
    kalender_future["tanggal"] = pd.to_datetime(kalender_future["year_month"] + "-01")
    kalender_future = kalender_future.reset_index(drop=True)

    return data, kalender_future


def cek_data_final(data):
    """Pengecekan akhir. Berhenti dengan pesan jika ada masalah."""
    assert data["year_month"].is_unique, "year_month duplikat"
    assert data["penumpang_ribu"].notna().all(), "Masih ada NaN di target"
    assert (data["penumpang_ribu"] > 0).all(), "Ada nilai target <= 0"

    rentang = pd.date_range(data["tanggal"].min(), data["tanggal"].max(), freq="MS")
    assert len(rentang) == len(data), "Ada bulan yang loncat"

    print("Semua pengecekan data_final LOLOS.")