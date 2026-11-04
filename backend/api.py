"""
backend/api.py
--------------
REST API Server (Flask) untuk Sistem Prediksi Penumpang KRL & Peringatan Risiko Kapasitas.
Menyajikan endpoint data inferensi machine learning, simulasi risiko,
serta melayani antarmuka web Front-End dashboard.
"""

import json
import logging
import os
import sys
from pathlib import Path

import pandas as pd
from flask import Flask, jsonify, request, send_from_directory

try:
    from flask_cors import CORS
except ImportError:
    CORS = None

# Konfigurasi direktori dasar
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR / "src"))

import config as cfg
import risk as rsk

# Inisialisasi Flask App
app = Flask(__name__, static_folder=str(BASE_DIR / "frontend"))

# Inisialisasi CORS
if CORS is not None:
    CORS(app, resources={r"/*": {"origins": "*"}})
else:
    @app.after_request
    def add_cors_headers(response):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
        response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
        return response

FOLDER_OUTPUT = BASE_DIR / "outputs"
FOLDER_PROCESSED = BASE_DIR / "data" / "processed"
FOLDER_FRONTEND = BASE_DIR / "frontend"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("krl_flask_api")


# ==============================================================================
# ERROR HANDLERS
# ==============================================================================
@app.errorhandler(400)
def bad_request(error):
    return jsonify({"error": "Bad Request", "detail": str(error)}), 400


@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Not Found", "detail": "Endpoint atau file tidak ditemukan."}), 404


@app.errorhandler(500)
def internal_server_error(error):
    return jsonify({"error": "Internal Server Error", "detail": str(error)}), 500


# ==============================================================================
# HELPER BUILD DATA BUNDLE (FRONT-END CONTRACT)
# ==============================================================================
def build_dashboard_bundle(ambang_kapasitas=cfg.AMBANG_KAPASITAS):
    """
    Menyusun data bundle lengkap (historis, forecast, evaluasi)
    sesuai struktur yang diharapkan oleh frontend/js/app.js.
    """
    # 1. Historis
    hist_file = FOLDER_PROCESSED / "data_final.csv"
    hist_list = []
    if hist_file.exists():
        df_hist = pd.read_csv(hist_file)
        for r in df_hist.itertuples():
            hist_list.append({
                "bulan": str(r.year_month),
                "nilai": int(round(float(r.penumpang_ribu))),
                "hari_kerja": int(r.jumlah_hari_kerja),
            })

    # 2. Forecast 6 bulan
    fc_file = FOLDER_OUTPUT / "prediksi_future_6bln.csv"
    fc_list = []
    if fc_file.exists():
        df_fc = pd.read_csv(fc_file)
        for r in df_fc.itertuples():
            h = int(r.horizon)
            bln = (pd.Timestamp("2026-08-01") + pd.DateOffset(months=h)).strftime("%Y-%m")
            fc_list.append({
                "bulan": bln,
                "horizon": h,
                "titik": round(float(r.y_pred_titik), 1),
                "l80": round(float(r.batas_bawah_80), 1),
                "u80": round(float(r.batas_atas_80), 1),
                "l95": round(float(r.batas_bawah_95), 1),
                "u95": round(float(r.batas_atas_95), 1),
            })

    # 3. Evaluasi
    metrik_file = FOLDER_OUTPUT / "metrik_komparasi_final.csv"
    eval_keseluruhan = []
    eval_pasca_covid = []
    if metrik_file.exists():
        df_m = pd.read_csv(metrik_file)
        for r in df_m.itertuples():
            item = {
                "model": str(r.model),
                "n": int(r.n),
                "mae": round(float(r.MAE), 1),
                "rmse": round(float(r.RMSE), 1),
                "mape": round(float(getattr(r, "MAPE_%", 0)), 2),
                "mase": round(float(r.MASE), 3),
            }
            if r.subset == "semua":
                eval_keseluruhan.append(item)
            elif r.subset in ["bersih", "pasca_covid"]:
                eval_pasca_covid.append(item)

    periode_label = "--"
    if hist_list:
        periode_label = f"{hist_list[0]['bulan']} s.d. {hist_list[-1]['bulan']}"

    return {
        "meta": {
            "sumber": "BPS & KAI Commuter (Pipeline ML Cerdas)",
            "satuan": "ribu penumpang",
            "periode_data": periode_label,
            "diperbarui": "2026-11-04",
            "model_terpilih": "LightGBM + Conformal CQR",
            "lebaran": ["2017-06", "2018-06", "2019-06", "2022-05", "2023-04", "2024-04", "2025-03", "2026-03"],
        },
        "ambang_kapasitas": {
            "nilai": float(ambang_kapasitas),
            "keterangan": "Batas teknis kapasitas operasional KRL Jabodetabek",
        },
        "historis": hist_list,
        "forecast": fc_list,
        "evaluasi": {
            "keseluruhan": eval_keseluruhan,
            "pasca_covid": eval_pasca_covid,
        },
    }


def sync_data_json():
    """Menyinkronkan file data/data.json agar kompatibel dengan live static server."""
    try:
        bundle = build_dashboard_bundle()
        target_paths = [
            BASE_DIR / "data" / "data.json",
            FOLDER_FRONTEND / "data" / "data.json",
        ]
        for p in target_paths:
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                json.dump(bundle, f, indent=2, ensure_ascii=False)
        logger.info("Sinkronisasi data/data.json selesai.")
    except Exception as exc:
        logger.warning(f"Gagal sinkronisasi data/data.json: {exc}")


# ==============================================================================
# REST API ENDPOINTS
# ==============================================================================
@app.route("/api/health", methods=["GET"])
def health_check():
    """Cek kesehatan server API Flask."""
    return jsonify({
        "status": "healthy",
        "service": "KRL Ridership Forecasting & Risk Capacity API (Flask)",
        "version": "1.0.0",
    })


@app.route("/api/forecast", methods=["GET"])
def get_forecast():
    """
    Mengambil data prakiraan 6 bulan ke depan beserta interval keyakinan 80% dan 95%
    dan klasifikasi risiko kapasitas.
    Query Params opsional:
      - ambang_kapasitas (float, default: 34000.0)
      - batas_waspada (float, default: 0.90)
      - basis_interval (str: "95" atau "80", default: "95")
    """
    path_file = FOLDER_OUTPUT / "prediksi_future_6bln.csv"
    if not path_file.exists():
        return jsonify({"error": "Data prakiraan belum di-generate"}), 404

    df = pd.read_csv(path_file)
    ambang = float(request.args.get("ambang_kapasitas", cfg.AMBANG_KAPASITAS))
    waspada = float(request.args.get("batas_waspada", cfg.BATAS_WASPADA))
    basis_interval = request.args.get("basis_interval", "95")
    kolom_hi = "batas_atas_80" if basis_interval == "80" else "batas_atas_95"

    df_risiko = rsk.klasifikasi_tabel_risiko(
        df,
        ambang_kapasitas=ambang,
        batas_waspada=waspada,
        kolom_batas_atas=kolom_hi,
    )
    return jsonify({
        "ambang_kapasitas_aktif": ambang,
        "batas_waspada_rasio": waspada,
        "basis_interval": basis_interval,
        "data": df_risiko.to_dict(orient="records"),
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
    body = request.get_json(silent=True) or {}
    ambang = float(body.get("ambang_kapasitas", cfg.AMBANG_KAPASITAS))
    waspada = float(body.get("batas_waspada", cfg.BATAS_WASPADA))
    kolom_hi = body.get("kolom_batas_atas", "batas_atas_95")

    path_file = FOLDER_OUTPUT / "prediksi_future_6bln.csv"
    if not path_file.exists():
        return jsonify({"error": "Data prakiraan tidak ditemukan"}), 404

    df = pd.read_csv(path_file)
    df_hasil = rsk.klasifikasi_tabel_risiko(
        df,
        ambang_kapasitas=ambang,
        batas_waspada=waspada,
        kolom_batas_atas=kolom_hi,
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
            "okupansi_maksimum_%": round(float(df_hasil["okupansi_batas_atas_%"].max()), 1),
        },
        "detail": df_hasil.to_dict(orient="records"),
    })


@app.route("/api/metrics", methods=["GET"])
def get_metrics():
    """
    Mengambil tabel skor komparasi performa model.
    Query Params:
      - subset (str: "bersih", "pasca_covid", "semua", default: "bersih")
      - horizon (int opsional: 1 s.d. 6)
    """
    horizon = request.args.get("horizon")
    if horizon:
        path_file = FOLDER_OUTPUT / "metrik_per_horizon_final.csv"
        if not path_file.exists():
            return jsonify({"error": "Data metrik per horizon tidak ditemukan"}), 404
        df = pd.read_csv(path_file)
        subset = request.args.get("subset", "bersih")
        df_sub = df[(df["subset"] == subset) & (df["horizon"] == int(horizon))]
        return jsonify(df_sub.to_dict(orient="records"))

    path_file = FOLDER_OUTPUT / "metrik_komparasi_final.csv"
    if not path_file.exists():
        return jsonify({"error": "Data metrik tidak ditemukan"}), 404

    df = pd.read_csv(path_file)
    subset = request.args.get("subset", "bersih")
    df_sub = df[df["subset"] == subset].sort_values("MASE")
    return jsonify(df_sub.to_dict(orient="records"))


@app.route("/api/sensitivity", methods=["GET"])
def get_sensitivity():
    """Mengambil tabel analisis sensitivitas pergeseran kapasitas (-10% s.d. +10%)."""
    path_file = FOLDER_OUTPUT / "analisis_sensitivitas_kapasitas.csv"
    if not path_file.exists():
        fc_path = FOLDER_OUTPUT / "prediksi_future_6bln.csv"
        if fc_path.exists():
            df_fc = pd.read_csv(fc_path)
            df_sens = rsk.analisis_sensitivitas(df_fc)
            return jsonify(df_sens.to_dict(orient="records"))
        return jsonify({"error": "Data analisis sensitivitas belum tersedia"}), 404

    df = pd.read_csv(path_file)
    return jsonify(df.to_dict(orient="records"))


@app.route("/api/passengers", methods=["GET"])
def get_passengers():
    """Mengambil deret waktu historis penumpang bulanan dari data BPS."""
    path_file = FOLDER_PROCESSED / "data_final.csv"
    if not path_file.exists():
        return jsonify({"error": "Data historis tidak ditemukan"}), 404

    df = pd.read_csv(path_file, parse_dates=["tanggal"])
    start = request.args.get("start")
    end = request.args.get("end")
    limit = int(request.args.get("limit", 200))

    if start:
        df = df[df["tanggal"] >= pd.Timestamp(start)]
    if end:
        df = df[df["tanggal"] <= pd.Timestamp(end)]

    df = df.head(limit)
    data = [
        {
            "period": r.tanggal.strftime("%Y-%m-%d"),
            "value_ribu": float(r.penumpang_ribu),
            "total_hari": int(r.total_hari),
            "hari_kerja": int(r.jumlah_hari_kerja),
            "is_lebaran": bool(r.is_lebaran),
            "is_covid": bool(r.is_covid),
        }
        for r in df.itertuples(index=False)
    ]
    return jsonify({"data": data})


@app.route("/api/models", methods=["GET"])
def get_models():
    """Mengambil daftar model peramalan yang terdaftar."""
    models = [
        {
            "run_id": "lgbm_cqr_v1",
            "algorithm": "LightGBM + CQR",
            "model_version": "1.0.0",
            "horizon_max": 6,
            "is_active": True,
            "description": "Multi-Horizon LightGBM dengan Conformalized Quantile Regression",
        },
        {
            "run_id": "sarimax_v1",
            "algorithm": "SARIMAX (Exogenous Calendar)",
            "model_version": "1.0.0",
            "horizon_max": 6,
            "is_active": False,
            "description": "SARIMAX(1,1,1)x(1,1,1,12) dengan fitur kalender hari kerja & Lebaran",
        },
        {
            "run_id": "ets_v1",
            "algorithm": "ETS (Holt-Winters)",
            "model_version": "1.0.0",
            "horizon_max": 6,
            "is_active": False,
            "description": "Exponential Smoothing Holt-Winters Musiman Additive",
        },
    ]
    return jsonify({"data": models})


@app.route("/api/data", methods=["GET"])
@app.route("/data/data.json", methods=["GET"])
def get_dashboard_data():
    """
    Menyajikan full data bundle JSON yang siap dikonsumsi langsung oleh Front-End dashboard.
    """
    ambang = float(request.args.get("ambang_kapasitas", cfg.AMBANG_KAPASITAS))
    bundle = build_dashboard_bundle(ambang_kapasitas=ambang)
    return jsonify(bundle)


# ==============================================================================
# FRONT-END STATIC SERVING
# ==============================================================================
@app.route("/", methods=["GET"])
def serve_index():
    """Melayani index.html front-end dashboard."""
    if (FOLDER_FRONTEND / "index.html").exists():
        return send_from_directory(str(FOLDER_FRONTEND), "index.html")
    return jsonify({
        "message": "KRL Forecast Flask API is running. Frontend directory not found.",
        "docs_url": "/api/health",
    })


@app.route("/<path:path>", methods=["GET"])
def serve_static(path):
    """Melayani aset statis front-end (css, js, img)."""
    file_path = FOLDER_FRONTEND / path
    if file_path.exists() and file_path.is_file():
        return send_from_directory(str(FOLDER_FRONTEND), path)
    return send_from_directory(str(FOLDER_FRONTEND), "index.html")


# ==============================================================================
# MAIN ENTRYPOINT
# ==============================================================================
sync_data_json()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"============================================================")
    print(f"  Starting KRL Forecast Flask API on http://127.0.0.1:{port}")
    print(f"  Dashboard Front-End : http://127.0.0.1:{port}/")
    print(f"  Health Check        : http://127.0.0.1:{port}/api/health")
    print(f"============================================================")
    app.run(host="127.0.0.1", port=port, debug=False)
