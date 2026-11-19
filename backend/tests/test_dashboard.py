from datetime import date

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.core.config import Settings
from backend.app.main import app
from backend.app.schemas.common import Interval
from backend.app.schemas.forecast import ForecastItem, ForecastResponse, RiskResult
from backend.app.services import dashboard as dashboard_module
from backend.app.services.dashboard import DashboardService


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


async def test_dashboard_forecast_matches_forecast_endpoint(client):
    dash = (await client.get("/api/v1/dashboard")).json()
    fc = (await client.get("/api/v1/forecasts/latest")).json()
    assert len(dash["forecast"]) == len(fc["data"]) == 6
    for row, item in zip(dash["forecast"], fc["data"], strict=True):
        assert row["bulan"] == item["period"][:7]
        assert row["titik"] == item["point"]
        assert row["u95"] == item["intervals"]["95"]["upper"]
        assert row["status"] == item["risk"]["status"]
    assert dash["meta"]["model_run_id"] == fc["meta"]["model_run_id"]
    assert dash["meta"]["model_terpilih"] == fc["meta"]["algorithm"]
    assert dash["meta"]["sumber_forecast"] == fc["meta"]["source"]


async def test_dashboard_capacity_override_and_legacy_aliases(client):
    res = await client.get("/api/v1/dashboard?ambang_kapasitas=35000")
    assert res.json()["ambang_kapasitas"]["nilai"] == 35000.0
    assert (await client.get("/api/data")).json()["forecast"]
    assert (await client.get("/api/v1/data")).json()["forecast"]
    assert (await client.get("/api/v1/dashboard?ambang_kapasitas=0")).status_code == 422


async def test_dashboard_lebaran_derived_from_data(client):
    lebaran = (await client.get("/api/v1/dashboard")).json()["meta"]["lebaran"]
    assert lebaran and all(len(m) == 7 and m[4] == "-" for m in lebaran)


async def test_dashboard_follows_active_model_metadata(monkeypatch):
    item = ForecastItem(
        period=date(2026, 9, 1), horizon=1, point=100.0,
        intervals={"80": Interval(lower=90.0, upper=110.0), "95": Interval(lower=80.0, upper=120.0)},
        risk=RiskResult(status="aman", utilization=0.1, capacity_ribu=1000.0),
    )

    async def fake_latest(self, **kwargs):
        return ForecastResponse(
            data=[item],
            meta={"algorithm": "Model Uji X", "model_run_id": "run_x", "source": "model",
                  "ambang_kapasitas_aktif": 1000.0, "data_through": "2026-08-01"},
        )

    monkeypatch.setattr(dashboard_module.ForecastService, "latest", fake_latest)
    data = await DashboardService(None, Settings(), None).bundle()
    assert data["forecast"] == [
        {"bulan": "2026-09", "horizon": 1, "titik": 100.0, "l80": 90.0, "u80": 110.0,
         "l95": 80.0, "u95": 120.0, "status": "aman"}
    ]
    assert data["meta"]["model_terpilih"] == "Model Uji X"
    assert data["meta"]["sumber_forecast"] == "model"
    assert data["ambang_kapasitas"]["nilai"] == 1000.0
