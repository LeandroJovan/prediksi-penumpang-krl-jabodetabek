"""
app.py
------
Dashboard Sistem Cerdas: Prediksi Penumpang KRL Jabodetabek & Peringatan Risiko Kapasitas.
Aplikasi interaktif berbasis Streamlit untuk peramalan time series dan dukungan keputusan operasional.
"""

import os
import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import streamlit as st

# Setup direktori proyek
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(BASE_DIR, "src"))

import config as cfg
import risk as rsk
import metrics as mt

# Konfigurasi Halaman Streamlit
st.set_page_config(
    page_title="Sistem Cerdas - Prediksi Penumpang KRL",
    page_icon="🚆",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Direktori data
FOLDER_PROCESSED = os.path.join(BASE_DIR, "data", "processed")
FOLDER_OUTPUT = os.path.join(BASE_DIR, "outputs")
FOLDER_GAMBAR = os.path.join(BASE_DIR, "reports", "figures")


@st.cache_data
def load_data():
    df_final = pd.read_csv(os.path.join(FOLDER_PROCESSED, "data_final.csv"), parse_dates=["tanggal"]).set_index("tanggal")
    y_hist = df_final["penumpang_ribu"].dropna()

    df_future = pd.read_csv(os.path.join(FOLDER_OUTPUT, "prediksi_future_6bln.csv"), parse_dates=["tanggal_target"])
    met_komparasi = pd.read_csv(os.path.join(FOLDER_OUTPUT, "metrik_komparasi_final.csv"))
    met_horizon = pd.read_csv(os.path.join(FOLDER_OUTPUT, "metrik_per_horizon_final.csv"))
    met_conformal = pd.read_csv(os.path.join(FOLDER_OUTPUT, "metrik_interval_conformal.csv"))

    return y_hist, df_future, met_komparasi, met_horizon, met_conformal


# Header Aplikasi
st.title("🚆 Sistem Cerdas: Prediksi Penumpang KRL Jabodetabek")
st.markdown(
    "**Proyek Sistem Cerdas — Program Studi Sains Data Terapan, PENS**  \n"
    "Peramalan deret waktu bulanan dengan **Kuantifikasi Ketidakpastian (Conformal Prediction)** "
    "dan **Sistem Peringatan Dini Risiko Kapasitas (*Capacity Risk Alert*)**."
)
st.write("---")

# Load Data
try:
    y_hist, df_future, met_komparasi, met_horizon, met_conformal = load_data()
    data_loaded = True
except Exception as e:
    st.error(f"Gagal memuat data: {e}. Pastikan file di folder `outputs/` sudah tersedia.")
    data_loaded = False

if data_loaded:
    # Sidebar Pengaturan
    st.sidebar.header("⚙️ Pengaturan Parameter")

    pilihan_model = st.sidebar.selectbox(
        "Pilih Model Utama:",
        ["LightGBM (Multi-Horizon)", "SARIMAX (0,1,1)(0,1,1)12"],
        index=0
    )

    level_interval = st.sidebar.radio(
        "Tingkat Interval Prediksi:",
        ["95% (Konservatif / Standar Risiko)", "80% (Moderat)"],
        index=0
    )
    is_95 = "95%" in level_interval
    kolom_lo = "batas_bawah_95" if is_95 else "batas_bawah_80"
    kolom_hi = "batas_atas_95" if is_95 else "batas_atas_80"

    ambang_kapasitas = st.sidebar.slider(
        "Ambang Kapasitas (Ribu Penumpang/Bulan):",
        min_value=28000.0,
        max_value=40000.0,
        value=float(cfg.AMBANG_KAPASITAS),
        step=500.0,
        help="Batas kapasitas maksimum sistem KRL. Default: 34.000 ribu (~34 juta penumpang/bulan)."
    )

    batas_waspada_rasio = st.sidebar.slider(
        "Batas Peringatan Waspada (% Ambang):",
        min_value=80,
        max_value=95,
        value=int(cfg.BATAS_WASPADA * 100),
        step=1
    ) / 100.0

    # Hitung status risiko dinamis berdasarkan slider
    df_risiko = rsk.klasifikasi_tabel_risiko(
        df_future,
        ambang_kapasitas=ambang_kapasitas,
        batas_waspada=batas_waspada_rasio,
        kolom_batas_atas=kolom_hi,
        kolom_titik="y_pred_titik"
    )

    # 1. Baris Metrik Ringkasan (KPI Cards)
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)

    rata_pred = df_risiko["y_pred_titik"].mean()
    puncak_batas_atas = df_risiko[kolom_hi].max()
    max_okupansi = df_risiko["okupansi_batas_atas_%"].max()

    # Status tertinggi
    if "Kritis" in df_risiko["status_risiko"].values:
        status_global = "KRITIS 🚨"
        warna_status = "red"
    elif "Waspada" in df_risiko["status_risiko"].values:
        status_global = "WASPADA ⚠️"
        warna_status = "orange"
    else:
        status_global = "AMAN ✅"
        warna_status = "green"

    kpi1.metric(
        "Rata-rata Prediksi 6 Bulan",
        f"{rata_pred:,.0f} ribu",
        f"{(rata_pred / ambang_kapasitas * 100):.1f}% Kapasitas"
    )
    kpi2.metric(
        "Batas Atas Maksimum",
        f"{puncak_batas_atas:,.0f} ribu",
        f"Okupansi {max_okupansi:.1f}%",
        delta_color="inverse"
    )
    kpi3.metric(
        "Ambang Batas Kapasitas",
        f"{ambang_kapasitas:,.0f} ribu",
        f"Waspada: >= {(ambang_kapasitas * batas_waspada_rasio):,.0f} ribu"
    )
    kpi4.metric(
        "Status Risiko Tertinggi",
        status_global,
        f"Skenario {level_interval.split()[0]}"
    )

    st.write("")

    # Tab Navigasi Utama
    tab_prakiraan, tab_evaluasi, tab_kebijakan = st.tabs([
        "📈 Prakiraan & Deteksi Risiko",
        "📊 Evaluasi & Validasi Model",
        "📋 Analisis Sensitivitas & Kebijakan"
    ])

    with tab_prakiraan:
        st.subheader("Prakiraan Permintaan KRL & Peringatan Risiko Kapasitas")

        col_chart, col_tabel = st.columns([7, 5])

        with col_chart:
            # Grafik Time Series Historis + Prediksi + Interval
            fig, ax = plt.subplots(figsize=(10, 5.2))
            hist_24 = y_hist.iloc[-24:]

            tgl_fut = pd.to_datetime(df_risiko["tanggal_target"])

            ax.plot(hist_24.index, hist_24.values, "k-o", label="Data Aktual (24 Bulan Terakhir)", linewidth=1.8, markersize=4)
            ax.plot(tgl_fut, df_risiko["y_pred_titik"], "b--o", label="Prakiraan Titik Permintaan", linewidth=2.2, markersize=5)

            # Fill interval
            label_band = f"Interval Prediksi {level_interval.split()[0]}"
            ax.fill_between(tgl_fut, df_risiko[kolom_lo], df_risiko[kolom_hi], color="blue", alpha=0.18, label=label_band)

            # Garis Ambang Kapasitas
            ax.axhline(ambang_kapasitas, color="red", linestyle="-", linewidth=2, label=f"Ambang Kritis ({ambang_kapasitas:,.0f}k)")
            ax.axhline(ambang_kapasitas * batas_waspada_rasio, color="orange", linestyle="--", linewidth=1.5, label=f"Batas Waspada ({ambang_kapasitas * batas_waspada_rasio:,.0f}k)")

            ax.set_ylabel("Penumpang (Ribu Orang)")
            ax.set_title("Visualisasi Interval Prediksi vs Ambang Kapasitas Infrastruktur", fontsize=11, fontweight="bold")
            ax.legend(loc="lower left", fontsize=8.5)
            ax.grid(True, alpha=0.3)
            plt.tight_layout()
            st.pyplot(fig)
            plt.close()

        with col_tabel:
            st.markdown("**Detail Prediksi 6 Bulan ke Depan**")

            tampil_tabel = pd.DataFrame({
                "Bulan Target": pd.to_datetime(df_risiko["tanggal_target"]).dt.strftime("%b %Y"),
                "Prediksi Titik": df_risiko["y_pred_titik"].apply(lambda x: f"{x:,.0f}"),
                "Batas Bawah": df_risiko[kolom_lo].apply(lambda x: f"{x:,.0f}"),
                "Batas Atas": df_risiko[kolom_hi].apply(lambda x: f"{x:,.0f}"),
                "Okupansi": df_risiko["okupansi_batas_atas_%"].apply(lambda x: f"{x:.1f}%"),
                "Status": df_risiko["status_risiko"]
            })

            def highlight_status(row):
                val = row["Status"]
                if val == "Kritis":
                    return ["background-color: #ffcccc; color: #990000; font-weight: bold"] * len(row)
                elif val == "Waspada":
                    return ["background-color: #fff0cc; color: #996600; font-weight: bold"] * len(row)
                else:
                    return ["background-color: #e6ffec; color: #006622; font-weight: bold"] * len(row)

            st.dataframe(tampil_tabel.style.apply(highlight_status, axis=1), use_container_width=True)

            if "Kritis" in df_risiko["status_risiko"].values:
                st.error("⚠️ **Peringatan**: Terdapat bulan yang berstatus **Kritis**! Batas atas ketidakpastian permintaan berpotensi melampaui kapasitas maksimum armada/stasiun.")
            elif "Waspada" in df_risiko["status_risiko"].values:
                st.warning("⚡ **Perhatian**: Status **Waspada** terdeteksi pada beberapa bulan ke depan. Direkomendasikan evaluasi frekuensi perjalanan.")
            else:
                st.success("✅ Seluruh horizon berada dalam batas **Aman**.")

    with tab_evaluasi:
        st.subheader("Validasi Empiris: Membuktikan Keunggulan Model Cerdas")

        c1, c2 = st.columns([6, 6])
        with c1:
            st.markdown("**1. Peringkat Model Berdasarkan MASE (Subset Bersih Pasca-COVID)**")
            st.caption("Nilai MASE < 1 membuktikan model cerdas berhasil mengalahkan baseline musiman.")
            sub_eval = met_komparasi[met_komparasi["subset"] == "bersih"].sort_values("MASE").reset_index(drop=True)
            st.dataframe(
                sub_eval[["model", "MAE", "RMSE", "MAPE_%", "MASE"]].style.format({
                    "MAE": "{:,.1f}",
                    "RMSE": "{:,.1f}",
                    "MAPE_%": "{:.2f}%",
                    "MASE": "{:.3f}"
                }),
                use_container_width=True
            )

        with c2:
            st.markdown("**2. Kualitas Interval Conformal Prediction**")
            st.caption("Mengukur probabilitas cakupan (*PICP*) dan lebar interval (*MPIW*).")
            st.dataframe(
                met_conformal[["horizon", "q_hat_80", "q_hat_95", "PICP_80_%", "PICP_95_%", "MPIW_95"]].style.format({
                    "q_hat_80": "{:,.1f}",
                    "q_hat_95": "{:,.1f}",
                    "PICP_80_%": "{:.1f}%",
                    "PICP_95_%": "{:.1f}%",
                    "MPIW_95": "{:,.1f}"
                }),
                use_container_width=True
            )

        st.write("---")
        st.markdown("**Grafik Performa Komparatif (Tersimpan di `reports/figures/`)**")
        g1, g2 = st.columns(2)
        with g1:
            if os.path.exists(os.path.join(FOLDER_GAMBAR, "lgbm_01_mase_per_horizon.png")):
                st.image(os.path.join(FOLDER_GAMBAR, "lgbm_01_mase_per_horizon.png"), caption="Perbandingan MASE per Horizon (Semua Model)")
        with g2:
            if os.path.exists(os.path.join(FOLDER_GAMBAR, "lgbm_04_feature_importance.png")):
                st.image(os.path.join(FOLDER_GAMBAR, "lgbm_04_feature_importance.png"), caption="Tingkat Kepentingan Fitur (Feature Importance)")

    with tab_kebijakan:
        st.subheader("Analisis Sensitivitas Ambang & Rekomendasi Manajerial")

        st.markdown("**1. Tabel Analisis Sensitivitas Skenario Kapasitas**")
        st.caption("Simulasi perubahan status risiko jika kapasitas efektif digeser ±5% dan ±10%.")
        df_sens = rsk.analisis_sensitivitas(df_future, ambang_dasar=ambang_kapasitas, kolom_batas_atas=kolom_hi)
        st.dataframe(df_sens, use_container_width=True)

        st.write("")
        st.markdown("### 📋 Pedoman Keputusan Operasional (PT KAI Commuter / DJKA)")
        st.info(
            "1. **Bulan Kritis (Status Kritis)**:  \n"
            "   - Operasikan stamformasi maksimum (SF-12) pada lintas utama (Bogor Line & Cikarang Line).  \n"
            "   - Percepat *turnaround time* di stasiun terminus (Jakarta Kota, Bogor, Bekasi).  \n"
            "   - Aktifkan skenario *crowd control* di stasiun transit Manggarai pada jam sibuk (06.30–08.30 dan 17.00–19.30).  \n\n"
            "2. **Bulan Waspada (Status Waspada)**:  \n"
            "   - Pantau tingkat kepadatan harian per lintas.  \n"
            "   - Koordinasi integrasi antarmoda dengan feeder busway Transjakarta untuk mencegah penumpukan di pintu keluar.  \n\n"
            "3. **Bulan Aman (Status Aman)**:  \n"
            "   - Gunakan jendela waktu untuk pemeliharaan rutin sarana dan prasarana gardu traksi tanpa mengorbankan frekuensi reguler."
        )

st.sidebar.write("---")
st.sidebar.caption("© 2026 Tim Proyek Sistem Cerdas — PENS")
