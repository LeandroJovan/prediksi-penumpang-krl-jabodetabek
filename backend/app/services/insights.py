import hashlib
import json

import httpx
from redis.asyncio import Redis

from backend.app.core.config import Settings
from backend.app.schemas.forecast import ForecastResponse
from backend.app.schemas.insight import InsightData, InsightResponse

ALLOWED_ACTIONS = [
    "monitor_capacity", "review_operational_readiness", "prepare_contingency_plan", "review_capacity_assumption",
]


def build_fact_pack(forecast: ForecastResponse, language: str) -> dict:
    facts = []
    for index, row in enumerate(forecast.data, 1):
        facts.extend([
            {"id": f"F{index}a", "kind": "forecast", "period": row.period.isoformat(), "horizon": row.horizon,
             "point": row.point, "lower95": row.intervals["95"].lower, "upper95": row.intervals["95"].upper},
            {"id": f"F{index}b", "kind": "risk", "period": row.period.isoformat(), "status": row.risk.status,
             "utilization": row.risk.utilization, "capacity_ribu": row.risk.capacity_ribu, "basis": row.risk.basis},
        ])
    return {"schema_version": "1.0", "language": language, "context": forecast.meta, "facts": facts, "allowed_actions": ALLOWED_ACTIONS}


def fallback(facts: dict) -> InsightData:
    language = facts["language"]
    risk = next((fact for fact in facts["facts"] if fact["kind"] == "risk"), None)
    status = risk["status"] if risk else "belum_ditentukan"
    period = risk["period"] if risk else "forecast"
    if language == "en":
        headline = f"Capacity risk for {period} is {status}."
        summary = "This summary is generated from validated forecast and risk calculations."
        limitation = "Forecast intervals represent uncertainty."
    else:
        headline = f"Risiko kapasitas untuk {period} berstatus {status}."
        summary = "Ringkasan ini dibuat dari hasil forecast dan risiko yang sudah tervalidasi."
        limitation = "Interval forecast menunjukkan ketidakpastian."
    recommendations = []
    if status in {"waspada", "kritis"}:
        recommendations = [{"action": "monitor_capacity", "priority": "high" if status == "kritis" else "medium", "rationale": summary, "fact_ids": [risk["id"]]}]
    return InsightData(risk_status=status, headline=headline, summary=summary, recommendations=recommendations, limitations=[limitation], fact_ids=[fact["id"] for fact in facts["facts"]], source="fallback")


class InsightService:
    def __init__(self, redis: Redis, settings: Settings) -> None:
        self.redis, self.settings = redis, settings

    async def generate(self, forecast: ForecastResponse, language: str = "id") -> InsightResponse:
        facts = build_fact_pack(forecast, language)
        canonical = json.dumps(facts, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(f"{canonical}:{self.settings.ollama_model}:{self.settings.ai_insight_prompt_version}".encode()).hexdigest()
        key = f"insight:v1:{digest}"
        cached = await self.redis.get(key)
        if cached:
            return InsightResponse.model_validate_json(cached)
        try:
            data = await self._ollama(facts)
        except Exception:
            data = fallback(facts)
        response = InsightResponse(data=data, meta={"language": language, "cached": False, "model": self.settings.ollama_model,
                                                     "prompt_version": self.settings.ai_insight_prompt_version,
                                                     "forecast_model_run_id": forecast.meta["model_run_id"]})
        await self.redis.set(key, response.model_dump_json(), ex=self.settings.ai_insight_cache_ttl_seconds)
        return response

    async def _ollama(self, facts: dict) -> InsightData:
        system = "Return JSON only. Use only supplied facts. Never alter risk_status. Actions must be from allowed_actions."
        payload = {"model": self.settings.ollama_model, "stream": False, "format": "json", "options": {"num_predict": 256, "num_ctx": 2048},
                   "messages": [{"role": "system", "content": system}, {"role": "user", "content": json.dumps(facts)}]}
        async with httpx.AsyncClient(timeout=self.settings.ollama_timeout_seconds) as client:
            response = await client.post(f"{self.settings.ollama_base_url}/api/chat", json=payload)
            response.raise_for_status()
        content = response.json()["message"]["content"]
        result = InsightData.model_validate_json(content)
        fact_ids = {fact["id"] for fact in facts["facts"]}
        risk_statuses = {fact["status"] for fact in facts["facts"] if fact["kind"] == "risk"}
        if not set(result.fact_ids).issubset(fact_ids) or result.risk_status not in risk_statuses:
            raise ValueError("Ungrounded AI response")
        if any(not set(item.fact_ids).issubset(fact_ids) for item in result.recommendations):
            raise ValueError("Invalid AI citations")
        return result.model_copy(update={"source": "ollama"})
