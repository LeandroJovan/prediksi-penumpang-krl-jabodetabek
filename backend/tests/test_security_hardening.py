import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.core.config import get_settings
from backend.app.core.security import SlidingWindowLimiter
from backend.app.main import app


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


def test_limiter_blocks_after_limit_and_recovers():
    limiter = SlidingWindowLimiter(window_seconds=60)
    assert limiter.check("ip", 2, now=0) is None
    assert limiter.check("ip", 2, now=1) is None
    retry = limiter.check("ip", 2, now=2)
    assert retry is not None and retry >= 1
    assert limiter.check("other", 2, now=2) is None
    assert limiter.check("ip", 2, now=61) is None


def test_limiter_zero_disables_and_is_bounded():
    limiter = SlidingWindowLimiter(window_seconds=60, max_keys=5)
    assert limiter.check("ip", 0) is None
    for i in range(20):
        limiter.check(f"k{i}", 5, now=float(i))
    assert len(limiter._hits) <= 5


async def test_request_id_valid_is_echoed_and_invalid_is_replaced(client):
    ok = await client.get("/api/v1/health/live", headers={"X-Request-ID": "abc-123"})
    assert ok.headers["X-Request-ID"] == "abc-123"
    bad = await client.get("/api/v1/health/live", headers={"X-Request-ID": "x y;<script>"})
    assert bad.headers["X-Request-ID"] != "x y;<script>"
    assert len(bad.headers["X-Request-ID"]) == 36


@pytest.mark.parametrize(
    "payload",
    [
        {"kolom_batas_atas": "drop_table"},
        {"horizons": [0]},
        {"horizons": [99]},
        {"ambang_kapasitas": 0},
        {"batas_waspada": 1.5},
        {"tidak_dikenal": 1},
    ],
)
async def test_simulate_rejects_invalid_payload(client, payload):
    res = await client.post("/api/v1/risk/simulate", json=payload)
    assert res.status_code == 422


async def test_simulate_returns_429_when_rate_limited(client, monkeypatch):
    from backend.app.core import security

    security._limiter._hits.clear()
    monkeypatch.setattr(get_settings(), "rate_limit_per_minute", 1)
    codes = [(await client.post("/api/v1/risk/simulate", json={})).status_code for _ in range(3)]
    assert codes[0] == 200
    assert 429 in codes[1:]
