"""
backend/api.py
--------------
REST API Server untuk Sistem Prediksi Penumpang KRL & Peringatan Risiko Kapasitas.
Menyajikan endpoint data inferensi machine learning untuk dikonsumsi oleh Front-End.
"""

import os
import sys
import pandas as pd
from flask import Flask, jsonify, request

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(BASE_DIR, "src"))

import config as cfg
import risk as rsk

app = Flask(__name__)

FOLDER_OUTPUT = os.path.join(BASE_DIR, "outputs")
FOLDER_PROCESSED = os.path.join(BASE_DIR, "data", "processed")


@app.route("/api/health", methods=["GET"])
def health_check():
    """Cek kesehatan server API."""
    return jsonify({
        "status": "healthy",
        "service": "KRL Ridership Forecasting & Risk Capacity API",
        "version": "1.0.0"
    })


@app.route("/api/forecast", methods=["GET"])
def get_forecast():
    """
    Mengambil data prakiraan 6 bulan ke depan beserta interval keyakinan 80% dan 95%.
    """
    path_file = os.path.join(FOLDER_OUTPUT, "prediksi_future_6bln.csv")
    if not os.path.exists(path_file):
        return jsonify({"error": "Data prakiraan belum di-generate"}), 404

    df = pd.read_csv(path_file)
    ambang = float(request.args.get("ambang_kapasitas", cfg.AMBANG_KAPASITAS))
    waspada = float(request.args.get("batas_waspada", cfg.BATAS_WASPADA))

    df_risiko = rsk.klasifikasi_tabel_risiko(df, ambang_kapasitas=ambang, batas_waspada=waspada)
    return jsonify({
        "ambang_kapasitas_aktif": ambang,
        "batas_waspada_rasio": waspada,
        "data": df_risiko.to_dict(orient="records")
    })


@app.route("/api/simulate-risk", methods=["POST"])
def simulate_risk():
    """
    Simulasi reaktif status risiko kapasitas berdasarkan input slider/parameter frontend.
    Payload JSON:
      {
        "ambang_kapasitas": 34000.0,
        "batas_waspada": 0.90,
        "kolom_batas_atas": "batas_atas_95"
      }
    """
    body = request.get_json() or {}
    ambang = float(body.get("ambang_kapasitas", cfg.AMBANG_KAPASITAS))
    waspada = float(body.get("batas_waspada", cfg.BATAS_WASPADA))
    kolom_hi = body.get("kolom_batas_atas", "batas_atas_95")

    path_file = os.path.join(FOLDER_OUTPUT, "prediksi_future_6bln.csv")
    if not os.path.exists(path_file):
        return jsonify({"error": "Data prakiraan tidak ditemukan"}), 404

    df = pd.read_csv(path_file)
    df_hasil = rsk.klasifikasi_tabel_risiko(
        df,
        ambang_kapasitas=ambang,
        batas_waspada=waspada,
        kolom_batas_atas=kolom_hi
    )

    status_tertinggi = "Aman"
    if "Kritis" in df_hasil["status_risiko"].values:
        status_tertinggi = "Kritis"
    elif "Waspada" in df_hasil["status_risiko"].values:
        status_tertinggi = "Waspada"

    return jsonify({
        "status_global": status_tertinggi,
        "ambang_kapasitas": ambang,
        "batas_waspada": waspada,
        "ringkasan": {
            "rata_rata_prediksi": round(float(df_hasil["y_pred_titik"].mean()), 1),
            "puncak_batas_atas": round(float(df_hasil[kolom_hi].max()), 1),
            "okupansi_maksimum_%": round(float(df_hasil["okupansi_batas_atas_%"].max()), 1)
        },
        "detail": df_hasil.to_dict(orient="records")
    })


@app.route("/api/metrics", methods=["GET"])
def get_metrics():
    """Mengambil tabel skor komparasi performa seluruh model."""
    path_file = os.path.join(FOLDER_OUTPUT, "metrik_komparasi_final.csv")
    if not os.path.exists(path_file):
        return jsonify({"error": "Data metrik tidak ditemukan"}), 404

    df = pd.read_csv(path_file)
    subset = request.args.get("subset", "bersih")
    df_sub = df[df["subset"] == subset].sort_values("MASE")
    return jsonify(df_sub.to_dict(orient="records"))


@app.route("/api/sensitivity", methods=["GET"])
def get_sensitivity():
    """Mengambil tabel analisis sensitivitas pergeseran kapasitas."""
    path_file = os.path.join(FOLDER_OUTPUT, "analisis_sensitivitas_kapasitas.csv")
    if not os.path.exists(path_file):
        return jsonify({"error": "Data analisis sensitivitas belum tersedia"}), 404

    df = pd.read_csv(path_file)
    return jsonify(df.to_dict(orient="records"))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting Backend API Server on port {port}...")
    app.run(host="0.0.0.0", port=port, debug=True)
