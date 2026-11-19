from datetime import date

import pytest

from backend.app.schemas.common import Interval
from backend.app.schemas.forecast import ForecastItem, ForecastResponse, RiskResult
from backend.app.services.insights import _validate_numbers, build_fact_pack, fallback


def make_forecast(statuses, points, uppers, capacity=34000.0):
    items = []
    for index, (status, point, upper) in enumerate(zip(statuses, points, uppers, strict=True), 1):
        utilization = None if capacity is None else upper / capacity
        month = 8 + index
        year = 2026 + (month - 1) // 12
        month = (month - 1) % 12 + 1
        items.append(ForecastItem(
            period=date(year, month, 1),
            horizon=index,
            point=point,
            intervals={
                "80": Interval(lower=point - 1000, upper=point + 1000),
                "95": Interval(lower=point - 2000, upper=upper),
            },
            risk=RiskResult(
                status=status,
                utilization=utilization,
                capacity_ribu=capacity,
            ),
        ))
    return ForecastResponse(data=items, meta={"model_run_id": "test-run", "unit": "ribu_orang"})


def test_five_of_six_kritis_uses_three_layers():
    forecast = make_forecast(
        statuses=["kritis", "kritis", "kritis", "kritis", "kritis", "waspada"],
        points=[30000, 31000, 30500, 32000, 30000, 29000],
        uppers=[34000, 35000, 34500, 36000, 34000, 33000],
    )
    facts = build_fact_pack(forecast, "id")
    assert facts["derived"]["n_kritis"] == 5
    assert facts["derived"]["n_waspada"] == 1
    assert facts["derived"]["peak_period"] == "2026-12-01"

    data = fallback(facts)
    assert "5 dari 6" in data.conclusion
    assert "Desember 2026" in data.conclusion
    assert len(data.points) == 3
    assert data.points[0].status == "kritis"
    assert "Perkiraan utama" in data.points[0].text
    assert "skenario padat" in data.points[0].text
    assert 2 <= len(data.actions) <= 3
    assert len(data.technical_details["months"]) == 6
    assert data.source == "fallback"
    _validate_numbers(data, facts)


def test_all_aman_is_reassuring():
    forecast = make_forecast(
        statuses=["aman"] * 6,
        points=[28000] * 6,
        uppers=[30000] * 6,
    )
    facts = build_fact_pack(forecast, "id")
    data = fallback(facts)
    assert "Semua 6 bulan" in data.conclusion
    assert "batas kapasitas" in data.conclusion
    assert "Kritis" not in data.conclusion
    assert data.points[0].status == "aman"
    assert 2 <= len(data.actions) <= 3
    _validate_numbers(data, facts)


def test_incomplete_data_is_handled():
    forecast = ForecastResponse(data=[], meta={})
    facts = build_fact_pack(forecast, "id")
    data = fallback(facts)
    assert "belum tersedia" in data.conclusion
    assert data.points == []
    assert data.actions == []
    assert data.technical_details["months"] == []
    assert data.risk_status == "belum_ditentukan"


def test_missing_capacity_is_explicit():
    forecast = make_forecast(
        statuses=["belum_ditentukan"] * 6,
        points=[30000] * 6,
        uppers=[34000] * 6,
        capacity=None,
    )
    facts = build_fact_pack(forecast, "id")
    data = fallback(facts)
    assert "Kapasitas layanan belum diatur" in data.conclusion
    assert data.points[0].status == "belum_ditentukan"
    assert data.risk_status == "belum_ditentukan"


def test_validator_rejects_invented_numbers():
    forecast = make_forecast(
        statuses=["kritis"] * 6,
        points=[30000] * 6,
        uppers=[35000] * 6,
    )
    facts = build_fact_pack(forecast, "id")
    data = fallback(facts)
    bad = data.model_copy(update={"conclusion": "Bulan ini 123.456 penumpang."})
    with pytest.raises(ValueError):
        _validate_numbers(bad, facts)


def test_waspada_ratio_follows_forecast_meta():
    forecast = make_forecast(["aman"] * 6, [20000] * 6, [25000] * 6)
    forecast.meta["batas_waspada_rasio"] = 0.8
    assert build_fact_pack(forecast, "id")["derived"]["waspada_ratio"] == 0.8
    del forecast.meta["batas_waspada_rasio"]
    assert build_fact_pack(forecast, "id")["derived"]["waspada_ratio"] == 0.9


async def test_generate_limits_concurrency_and_avoids_stampede(monkeypatch):
    import asyncio

    from backend.app.core.cache import InMemoryCache
    from backend.app.core.config import Settings
    from backend.app.services.insights import InsightService, fallback

    service = InsightService(InMemoryCache(), Settings(ollama_max_concurrency=1))
    state = {"calls": 0, "active": 0, "peak": 0}

    async def fake_ollama(facts):
        state["calls"] += 1
        state["active"] += 1
        state["peak"] = max(state["peak"], state["active"])
        await asyncio.sleep(0.05)
        state["active"] -= 1
        return fallback(facts)

    monkeypatch.setattr(service, "_ollama", fake_ollama)
    forecast = make_forecast(["aman"] * 6, [20000] * 6, [25000] * 6)
    results = await asyncio.gather(*[service.generate(forecast) for _ in range(5)])

    assert state["peak"] == 1
    assert state["calls"] == 1  # request identik berbagi satu panggilan LLM
    assert sum(r.meta["cached"] for r in results) == 4


def test_fallback_english_has_no_indonesian_text_and_valid_numbers():
    forecast = make_forecast(
        statuses=["kritis", "waspada", "aman", "aman", "aman", "aman"],
        points=[30000, 31000, 20000, 21000, 22000, 23000],
        uppers=[34000, 33000, 25000, 26000, 27000, 28000],
    )
    facts = build_fact_pack(forecast, "en")
    data = fallback(facts)

    assert "December 2026" in data.conclusion or "September 2026" in data.conclusion
    assert "million passengers" in data.points[0].text
    assert "capacity" in data.points[0].text
    text = " ".join([data.conclusion, data.summary, *[p.text for p in data.points], *data.actions])
    for indonesian in ("juta", "bulan", "kapasitas", "Perkiraan", "Tinjau"):
        assert indonesian not in text
    # Pemisah desimal bergaya Inggris (titik) dan lolos validasi angka
    assert "," not in data.points[0].text.split("million")[0].split("estimate")[-1]
    _validate_numbers(data, facts)


def test_fallback_language_default_and_unknown_use_indonesian():
    forecast = make_forecast(["aman"] * 6, [20000] * 6, [25000] * 6)
    assert "Semua 6 bulan" in fallback(build_fact_pack(forecast, "id")).conclusion
    assert "Semua 6 bulan" in fallback(build_fact_pack(forecast, "xx")).conclusion
    assert "All 6 upcoming months" in fallback(build_fact_pack(forecast, "en")).conclusion


def test_english_number_and_month_formatting():
    from backend.app.services.insights import _fmt_juta, _fmt_one, _period_label

    assert _fmt_one(1234.56, "en") == "1,234.6"
    assert _fmt_one(1234.56, "id") == "1.234,6"
    assert _fmt_juta(30135, "en") == "30.1"
    assert _period_label("2026-12-01", "en") == "December 2026"
    assert _period_label("2026-12-01") == "Desember 2026"


async def test_endpoint_language_en_returns_english(monkeypatch):
    from httpx import ASGITransport, AsyncClient

    from backend.app.main import app
    from backend.app.services import insights as mod

    async def fail(self, facts):
        raise RuntimeError("ollama off")

    monkeypatch.setattr(mod.InsightService, "_ollama", fail)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/v1/insights/latest?language=en")
    assert res.status_code == 200
    assert res.json()["data"]["source"] == "fallback"
    assert "juta" not in res.json()["data"]["conclusion"]
