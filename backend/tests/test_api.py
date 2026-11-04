import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.main import app
from backend.cli.seed_data import seed_all


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_seed_database():
    # Verify idempotent seed function runs without errors
    await seed_all()


@pytest.mark.asyncio
async def test_health_endpoints(client: AsyncClient):
    res_live = await client.get("/api/v1/health/live")
    assert res_live.status_code == 200
    assert res_live.json()["status"] in ["healthy", "ok"]

    res_health = await client.get("/api/v1/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "healthy"

    res_ready = await client.get("/api/v1/health/ready")
    assert res_ready.status_code == 200
    assert res_ready.json()["status"] == "ready"


@pytest.mark.asyncio
async def test_forecast_latest(client: AsyncClient):
    res = await client.get("/api/v1/forecasts/latest")
    assert res.status_code == 200
    payload = res.json()
    assert "data" in payload
    assert "meta" in payload
    assert len(payload["data"]) == 6
    assert payload["data"][0]["horizon"] == 1
    assert "80" in payload["data"][0]["intervals"]
    assert "95" in payload["data"][0]["intervals"]
    assert payload["data"][0]["risk"]["status"] in ["aman", "waspada", "kritis"]


@pytest.mark.asyncio
async def test_forecast_invalid_horizon(client: AsyncClient):
    res = await client.get("/api/v1/forecasts/latest?horizon=99")
    assert res.status_code == 422
    data = res.json()
    assert "detail" in data
    assert data["status"] == 422


@pytest.mark.asyncio
async def test_forecast_with_capacity_and_horizon_filter(client: AsyncClient):
    res = await client.get("/api/v1/forecasts/latest?horizon=1&horizon=2&ambang_kapasitas=32000&basis_interval=95")
    assert res.status_code == 200
    payload = res.json()
    assert len(payload["data"]) == 2
    assert payload["data"][0]["horizon"] == 1
    assert payload["data"][1]["horizon"] == 2
    assert payload["meta"]["ambang_kapasitas_aktif"] == 32000.0


@pytest.mark.asyncio
async def test_risk_simulate(client: AsyncClient):
    payload = {
        "ambang_kapasitas": 31000.0,
        "batas_waspada": 0.90,
        "kolom_batas_atas": "batas_atas_95",
        "capacity_weekday_ribu": 1100.0,
        "capacity_weekend_ribu": 850.0,
        "horizons": [1, 2, 3],
    }
    res = await client.post("/api/v1/risk/simulate", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "data" in data
    assert len(data["data"]) == 3
    for item in data["data"]:
        assert item["risk"]["status"] in ["aman", "waspada", "kritis"]


@pytest.mark.asyncio
async def test_risk_sensitivity(client: AsyncClient):
    res = await client.get("/api/v1/risk/sensitivity")
    assert res.status_code == 200
    data = res.json()
    assert "data" in data
    assert len(data["data"]) > 0


@pytest.mark.asyncio
async def test_metrics_endpoint(client: AsyncClient):
    res = await client.get("/api/v1/metrics?subset=bersih")
    assert res.status_code == 200
    data = res.json()
    assert "data" in data
    assert len(data["data"]) > 0

    res_h = await client.get("/api/v1/metrics?subset=bersih&horizon=1")
    assert res_h.status_code == 200
    assert len(res_h.json()["data"]) > 0


@pytest.mark.asyncio
async def test_passengers_endpoint(client: AsyncClient):
    res = await client.get("/api/v1/passengers?limit=12")
    assert res.status_code == 200
    data = res.json()
    assert "data" in data
    assert len(data["data"]) == 12

    res_filtered = await client.get("/api/v1/passengers?start=2025-01-01&end=2025-06-01")
    assert res_filtered.status_code == 200
    assert len(res_filtered.json()["data"]) > 0


@pytest.mark.asyncio
async def test_models_endpoint(client: AsyncClient):
    res = await client.get("/api/v1/models")
    assert res.status_code == 200
    data = res.json()
    assert "data" in data
    assert len(data["data"]) > 0

    first_model = data["data"][0]["run_id"]
    res_detail = await client.get(f"/api/v1/models/{first_model}")
    assert res_detail.status_code == 200

    res_not_found = await client.get("/api/v1/models/non_existent_model")
    assert res_not_found.status_code == 404


@pytest.mark.asyncio
async def test_meta_endpoint(client: AsyncClient):
    res = await client.get("/api/v1/meta")
    assert res.status_code == 200
    data = res.json()["data"]
    assert "data_start" in data
    assert "data_through" in data
    assert "active_model" in data


@pytest.mark.asyncio
async def test_insights_endpoint(client: AsyncClient):
    res = await client.get("/api/v1/insights/latest?language=id")
    assert res.status_code == 200
    payload = res.json()
    assert "data" in payload
    assert payload["data"]["risk_status"] in ["aman", "waspada", "kritis", "belum_ditentukan"]
    assert "headline" in payload["data"]

    res_en = await client.get("/api/v1/insights/latest?language=en")
    assert res_en.status_code == 200


@pytest.mark.asyncio
async def test_frontend_mount(client: AsyncClient):
    res = await client.get("/")
    assert res.status_code == 200
    assert "text/html" in res.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_dashboard_bundle_endpoint(client: AsyncClient):
    res1 = await client.get("/api/data")
    assert res1.status_code == 200
    data1 = res1.json()
    assert "historis" in data1
    assert "forecast" in data1
    assert "evaluasi" in data1
    assert len(data1["forecast"]) == 6

    res2 = await client.get("/api/v1/data?ambang_kapasitas=35000")
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["ambang_kapasitas"]["nilai"] == 35000.0

