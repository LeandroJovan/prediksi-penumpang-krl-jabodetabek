"""
risk.py
-------
Lapisan keputusan dan evaluasi risiko kapasitas KRL Jabodetabek.

Menerjemahkan batas atas interval prediksi (khususnya 95%) menjadi indikator
status risiko operasional terhadap batas kapasitas infrastruktur.

Kategori Status Risiko:
  - Aman    : Batas atas < 90% ambang kapasitas (risiko kelebihan beban sangat rendah)
  - Waspada : Batas atas antara 90% - 100% ambang kapasitas (potensi kepadatan tinggi)
  - Kritis  : Batas atas >= 100% ambang kapasitas (potensi bottle-neck & overcapacity)
"""

import numpy as np
import pandas as pd

AMBANG_KAPASITAS_DEFAULT = 34000.0  # Ribu penumpang per bulan (~34 juta)
BATAS_WASPADA_DEFAULT = 0.90       # 90% dari ambang kapasitas


def tentukan_status_risiko(nilai_batas_atas, ambang_kapasitas=AMBANG_KAPASITAS_DEFAULT,
                           batas_waspada=BATAS_WASPADA_DEFAULT):
    """
    Menentukan status risiko untuk satu nilai batas atas prediksi.
    """
    if pd.isna(nilai_batas_atas) or pd.isna(ambang_kapasitas):
        return "Tidak Diketahui"

    ambang_waspada = batas_waspada * ambang_kapasitas

    if nilai_batas_atas < ambang_waspada:
        return "Aman"
    elif nilai_batas_atas < ambang_kapasitas:
        return "Waspada"
    else:
        return "Kritis"


def klasifikasi_tabel_risiko(df_prediksi, ambang_kapasitas=AMBANG_KAPASITAS_DEFAULT,
                             batas_waspada=BATAS_WASPADA_DEFAULT,
                             kolom_batas_atas="batas_atas_95",
                             kolom_titik="y_pred_titik"):
    """
    Menambahkan indikator kapasitas dan status risiko pada tabel prakiraan masa depan.

    df_prediksi : DataFrame dengan kolom tanggal_target, kolom_titik, kolom_batas_atas.
    Return      : DataFrame salinan lengkap dengan kolom rasio & status risiko.
    """
    df = df_prediksi.copy()

    df["ambang_kapasitas"] = ambang_kapasitas
    df["ambang_waspada"] = ambang_kapasitas * batas_waspada

    if kolom_titik in df.columns:
        df["okupansi_titik_%"] = (df[kolom_titik] / ambang_kapasitas * 100).round(1)

    df["okupansi_batas_atas_%"] = (df[kolom_batas_atas] / ambang_kapasitas * 100).round(1)

    df["status_risiko"] = [
        tentukan_status_risiko(val, ambang_kapasitas, batas_waspada)
        for val in df[kolom_batas_atas]
    ]

    return df


def analisis_sensitivitas(df_prediksi, ambang_dasar=AMBANG_KAPASITAS_DEFAULT,
                          daftar_pergeseran=(-0.10, -0.05, 0.0, 0.05, 0.10),
                          kolom_batas_atas="batas_atas_95"):
    """
    Analisis sensitivitas risiko kapasitas jika ambang bergeser (misal -10%, -5%, +5%, +10%).

    Return: DataFrame rangkuman status risiko per skenario kapasitas.
    """
    hasil_skenario = []

    for delta in daftar_pergeseran:
        ambang_simulasi = ambang_dasar * (1.0 + delta)
        nama_skenario = f"{int(delta * 100):+d}% ({ambang_simulasi:,.0f} ribu)" if delta != 0 else f"Dasar ({ambang_dasar:,.0f} ribu)"

        baris = {"skenario": nama_skenario, "ambang_kapasitas": ambang_simulasi}
        for _, row in df_prediksi.iterrows():
            tgl = pd.to_datetime(row["tanggal_target"]).strftime("%b %Y")
            val = row[kolom_batas_atas]
            st = tentukan_status_risiko(val, ambang_simulasi)
            baris[tgl] = st

        hasil_skenario.append(baris)

    return pd.DataFrame(hasil_skenario)
