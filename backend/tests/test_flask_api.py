import json
import pytest

from backend.api import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_flask_health_check(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "healthy"


def test_flask_get_forecast(client):
    res = client.get("/api/forecast")
    assert res.status_code == 200
    data = res.get_json()
    assert "data" in data
    assert len(data["data"]) == 6
    first = data["data"][0]
    assert "y_pred_titik" in first
    assert "status_risiko" in first


def test_flask_get_forecast_custom_capacity(client):
    res = client.get("/api/forecast?ambang_kapasitas=31000&batas_waspada=0.85&basis_interval=80")
    assert res.status_code == 200
    data = res.get_json()
    assert data["ambang_kapasitas_aktif"] == 31000.0
    assert data["batas_waspada_rasio"] == 0.85


def test_flask_simulate_risk(client):
    payload = {
        "ambang_kapasitas": 32000.0,
        "batas_waspada": 0.90,
        "kolom_batas_atas": "batas_atas_95",
    }
    res = client.post(
        "/api/simulate-risk",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert res.status_code == 200
    data = res.get_json()
    assert "status_global" in data
    assert data["status_global"] in ["Aman", "Waspada", "Kritis"]
    assert "ringkasan" in data
    assert "detail" in data
    assert len(data["detail"]) == 6


def test_flask_get_metrics(client):
    res = client.get("/api/metrics?subset=bersih")
    assert res.status_code == 200
    data = res.get_json()
    assert isinstance(data, list)
    assert len(data) > 0

    res_h = client.get("/api/metrics?subset=bersih&horizon=1")
    assert res_h.status_code == 200
    data_h = res_h.get_json()
    assert isinstance(data_h, list)


def test_flask_get_sensitivity(client):
    res = client.get("/api/sensitivity")
    assert res.status_code == 200
    data = res.get_json()
    assert isinstance(data, list)
    assert len(data) > 0


def test_flask_get_passengers(client):
    res = client.get("/api/passengers?limit=6")
    assert res.status_code == 200
    data = res.get_json()
    assert "data" in data
    assert len(data["data"]) == 6


def test_flask_get_models(client):
    res = client.get("/api/models")
    assert res.status_code == 200
    data = res.get_json()
    assert "data" in data
    assert len(data["data"]) > 0


def test_flask_dashboard_data_bundle(client):
    res = client.get("/api/data")
    assert res.status_code == 200
    data = res.get_json()
    assert "meta" in data
    assert "ambang_kapasitas" in data
    assert "historis" in data
    assert "forecast" in data
    assert "evaluasi" in data

    res_static = client.get("/data/data.json")
    assert res_static.status_code == 200


def test_flask_frontend_static(client):
    res = client.get("/")
    assert res.status_code == 200
    assert b"<!DOCTYPE html>" in res.data or b"<html" in res.data



# --- Validasi input & penanganan error (audit QA) ---
@pytest.mark.parametrize(
    "query",
    [
        "ambang_kapasitas=abc",
        "ambang_kapasitas=0",
        "ambang_kapasitas=-5",
        "ambang_kapasitas=nan",
        "batas_waspada=1.5",
        "basis_interval=70",
    ],
)
def test_flask_forecast_rejects_invalid_query(query):
    res = app.test_client().get(f"/api/forecast?{query}")
    assert res.status_code == 400
    assert res.get_json()["error"] == "Bad Request"


@pytest.mark.parametrize(
    "body",
    [
        {"ambang_kapasitas": 0},
        {"batas_waspada": "x"},
        {"kolom_batas_atas": "bukan_kolom"},
        [1, 2],
    ],
)
def test_flask_simulate_rejects_invalid_body(body):
    res = app.test_client().post("/api/simulate-risk", json=body)
    assert res.status_code == 400


def test_flask_unknown_api_path_is_json_404():
    res = app.test_client().get("/api/tidak-ada")
    assert res.status_code == 404
    assert res.get_json()["error"] == "Not Found"


def test_flask_metrics_and_passengers_reject_bad_numbers():
    client = app.test_client()
    assert client.get("/api/metrics?horizon=abc").status_code == 400
    assert client.get("/api/passengers?limit=-1").status_code == 400
    assert client.get("/api/passengers?start=bukan-tanggal").status_code == 400
