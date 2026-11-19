import hashlib
import json
import logging
import re
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP

import httpx
from redis.asyncio import Redis

from backend.app.core.config import Settings
from backend.app.schemas.forecast import ForecastResponse
from backend.app.schemas.insight import InsightData, InsightPoint, InsightResponse, Recommendation

logger = logging.getLogger("krl_backend.insights")

ALLOWED_ACTIONS = [
    "monitor_capacity", "review_operational_readiness", "prepare_contingency_plan", "review_capacity_assumption",
]

MONTHS_ID = [
    "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
]


def _fmt_int(value: float | int | None) -> str:
    if value is None:
        return "--"
    return f"{value:,.0f}".replace(",", ".")


def _fmt_one(value: float | int | None) -> str:
    if value is None:
        return "--"
    rounded = Decimal(str(value)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    return f"{rounded:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _fmt_juta(value: float | int | None) -> str:
    if value is None:
        return "--"
    return _fmt_one(float(value) / 1000.0)


def _fmt_pct(value: float | int | None) -> str:
    if value is None:
        return "--"
    return _fmt_one(value)


def _period_label(value: str | date | datetime | None) -> str:
    if value is None:
        return "-"
    if isinstance(value, (date, datetime)):
        year, month = value.year, value.month
    else:
        parts = str(value).split("-")
        if len(parts) < 2:
            return str(value)
        year, month = int(parts[0]), int(parts[1])
    if 1 <= month <= 12:
        return f"{MONTHS_ID[month - 1]} {year}"
    return str(value)


def _summary_from_forecast(forecast: ForecastResponse) -> dict:
    rows = list(forecast.data)
    n = len(rows)
    kritis = [r for r in rows if r.risk.status == "kritis"]
    waspada = [r for r in rows if r.risk.status == "waspada"]
    aman = [r for r in rows if r.risk.status == "aman"]
    peak = max(rows, key=lambda r: r.intervals["95"].upper) if rows else None
    lowest = min(
        rows,
        key=lambda r: r.risk.utilization if r.risk.utilization is not None else float("inf"),
    ) if rows else None
    capacity = rows[0].risk.capacity_ribu if rows else None
    months = [{
        "period": r.period.isoformat(),
        "point": r.point,
        "lower80": r.intervals["80"].lower,
        "upper80": r.intervals["80"].upper,
        "lower95": r.intervals["95"].lower,
        "upper95": r.intervals["95"].upper,
        "utilization": r.risk.utilization,
        "status": r.risk.status,
    } for r in rows]
    derived = {
        "n_months": n,
        "n_kritis": len(kritis),
        "n_waspada": len(waspada),
        "n_aman": len(aman),
        "overall_status": "kritis" if kritis else "waspada" if waspada else "aman" if aman else "belum_ditentukan",
        "peak_period": peak.period.isoformat() if peak else None,
        "peak_point": peak.point if peak else None,
        "peak_upper95": peak.intervals["95"].upper if peak else None,
        "peak_utilization": peak.risk.utilization if peak else None,
        "peak_status": peak.risk.status if peak else "belum_ditentukan",
        "lowest_period": lowest.period.isoformat() if lowest else None,
        "lowest_upper95": lowest.intervals["95"].upper if lowest else None,
        "lowest_utilization": lowest.risk.utilization if lowest else None,
        "lowest_status": lowest.risk.status if lowest else "belum_ditentukan",
        "capacity_ribu": capacity,
        "waspada_ratio": 0.9,
        "kritis_ratio": 1.0,
        "months": months,
    }
    return {"rows": rows, "derived": derived}


def build_fact_pack(forecast: ForecastResponse, language: str) -> dict:
    facts = []
    for index, row in enumerate(forecast.data, 1):
        facts.extend([
            {"id": f"F{index}a", "kind": "forecast", "period": row.period.isoformat(), "horizon": row.horizon,
             "point": row.point, "lower95": row.intervals["95"].lower, "upper95": row.intervals["95"].upper},
            {"id": f"F{index}b", "kind": "risk", "period": row.period.isoformat(), "status": row.risk.status,
             "utilization": row.risk.utilization, "capacity_ribu": row.risk.capacity_ribu, "basis": row.risk.basis},
        ])
    summary = _summary_from_forecast(forecast)
    facts.append({"id": "D1", "kind": "summary", **summary["derived"]})
    return {
        "schema_version": "1.0",
        "language": language,
        "context": forecast.meta,
        "facts": facts,
        "derived": summary["derived"],
        "allowed_actions": ALLOWED_ACTIONS,
    }


def _fallback_recommendations(actions: list[str], fact_ids: list[str], high: bool) -> list[Recommendation]:
    return [
        Recommendation(
            action="monitor_capacity",
            priority="high" if high else "medium",
            rationale=action,
            fact_ids=fact_ids or ["D1"],
        )
        for action in actions[:3]
    ]


def fallback(facts: dict) -> InsightData:
    derived = facts.get("derived", {})
    n = int(derived.get("n_months") or 0)
    n_kritis = int(derived.get("n_kritis") or 0)
    n_waspada = int(derived.get("n_waspada") or 0)
    n_aman = int(derived.get("n_aman") or 0)
    capacity = derived.get("capacity_ribu")
    peak_period = derived.get("peak_period")
    peak_upper = derived.get("peak_upper95")
    peak_util = derived.get("peak_utilization")
    peak_status = derived.get("peak_status") or "belum_ditentukan"
    lowest_period = derived.get("lowest_period")
    lowest_upper = derived.get("lowest_upper95")
    lowest_util = derived.get("lowest_utilization")
    lowest_status = derived.get("lowest_status") or "belum_ditentukan"
    months = derived.get("months", [])
    certainty = "Perkiraan masih bisa meleset cukup jauh; gunakan sebagai arahan perencanaan, bukan angka pasti."
    risk_fact_ids = [fact["id"] for fact in facts.get("facts", []) if fact.get("kind") == "risk"]
    fact_ids = [fact["id"] for fact in facts.get("facts", [])]

    if n == 0:
        conclusion = "Data prediksi belum tersedia. Insight akan muncul setelah data forecast tersedia."
        return InsightData(
            risk_status="belum_ditentukan",
            headline=conclusion,
            summary=conclusion,
            recommendations=[],
            limitations=[],
            fact_ids=fact_ids,
            source="fallback",
            conclusion=conclusion,
            points=[],
            actions=[],
            technical_details={"capacity_ribu": capacity, "unit": "ribu_orang", "months": months},
        )

    has_capacity = capacity is not None and capacity > 0
    if not has_capacity:
        points = [
            InsightPoint(
                status="belum_ditentukan",
                text=(
                    f"Bulan paling padat: {_period_label(peak_period)}. "
                    f"Perkiraan utama {_fmt_juta(derived.get('peak_point'))} juta penumpang; "
                    f"skenario padat {_fmt_juta(peak_upper)} juta. "
                    "Kapasitas layanan belum diatur, sehingga status risiko belum bisa ditentukan."
                ),
            ),
            InsightPoint(status="waspada", text=certainty),
        ]
        actions = [
            "Lengkapi parameter kapasitas layanan agar status risiko dapat dihitung.",
            "Tinjau ulang perkiraan saat data aktual bulan baru masuk.",
        ]
        conclusion = (
            "Kapasitas layanan belum diatur, sehingga status risiko belum bisa ditentukan. "
            "Perkiraan penumpang tetap dapat dilihat pada detail teknis."
        )
        return InsightData(
            risk_status="belum_ditentukan",
            headline=conclusion,
            summary=points[0].text,
            recommendations=_fallback_recommendations(actions, risk_fact_ids, False),
            limitations=[certainty],
            fact_ids=fact_ids,
            source="fallback",
            conclusion=conclusion,
            points=points[:3],
            actions=actions,
            technical_details={"capacity_ribu": capacity, "unit": "ribu_orang", "months": months},
        )

    if n_kritis > 0:
        conclusion = (
            f"{n_kritis} dari {n} bulan ke depan diperkirakan berisiko melebihi kapasitas layanan. "
            f"Puncaknya {_period_label(peak_period)}."
        )
    elif n_waspada > 0:
        conclusion = (
            f"Tidak ada bulan yang diperkirakan melebihi kapasitas, tetapi "
            f"{n_waspada} dari {n} bulan perlu diawasi. Puncaknya {_period_label(peak_period)}."
        )
    else:
        conclusion = f"Semua {n} bulan ke depan diperkirakan masih dalam batas kapasitas."

    peak_point = derived.get("peak_point") or 0
    if capacity and peak_point < capacity:
        comparison = "di bawah"
    elif capacity and peak_point > capacity:
        comparison = "di atas"
    else:
        comparison = "setara dengan"
    points = [
        InsightPoint(
            status=peak_status,
            text=(
                f"Bulan paling padat: {_period_label(peak_period)}. "
                f"Perkiraan utama {_fmt_juta(peak_point)} juta penumpang "
                f"({comparison} kapasitas {_fmt_juta(capacity)} juta); "
                f"skenario padat {_fmt_juta(peak_upper)} juta "
                f"({_fmt_pct((peak_util or 0) * 100)}% dari kapasitas)."
            ),
        ),
    ]
    if lowest_period:
        if lowest_status == "aman":
            lowest_label = "Bulan yang mulai longgar"
        elif lowest_status == "waspada":
            lowest_label = "Bulan yang perlu diawasi"
        else:
            lowest_label = "Bulan dengan tekanan paling rendah"
        points.append(InsightPoint(
            status=lowest_status,
            text=(
                f"{lowest_label}: {_period_label(lowest_period)}. "
                f"Skenario padat {_fmt_juta(lowest_upper)} juta "
                f"({_fmt_pct((lowest_util or 0) * 100)}% dari kapasitas)."
            ),
        ))
    points.append(InsightPoint(status="waspada", text=certainty))

    actions = []
    if n_kritis > 0:
        actions.append(f"Tambah perjalanan atau rangkaian pada bulan Kritis, terutama {_period_label(peak_period)}.")
    if n_kritis > 0 or n_waspada > 0:
        actions.append(f"Atur arus penumpang di stasiun padat pada jam sibuk, terutama {_period_label(peak_period)}.")
    else:
        actions.append("Pertahankan jadwal operasional dan pantau data aktual bulan baru.")
    actions.append("Tinjau ulang perkiraan saat data aktual bulan baru masuk.")

    risk_status = "kritis" if n_kritis > 0 else "waspada" if n_waspada > 0 else "aman"
    return InsightData(
        risk_status=risk_status,
        headline=conclusion,
        summary=points[0].text,
        recommendations=_fallback_recommendations(actions, risk_fact_ids, n_kritis > 0),
        limitations=[certainty],
        fact_ids=fact_ids,
        source="fallback",
        conclusion=conclusion,
        points=points[:3],
        actions=actions[:3],
        technical_details={"capacity_ribu": capacity, "unit": "ribu_orang", "months": months},
    )


def _number_candidates(token: str) -> set[float]:
    candidates: set[float] = set()
    for cleaned in {token.replace(".", "").replace(",", "."), token.replace(",", "")}:
        try:
            candidates.add(float(cleaned))
        except ValueError:
            pass
    return candidates


def _collect_numbers(value, out: set[float]) -> None:
    if isinstance(value, dict):
        for item in value.values():
            _collect_numbers(item, out)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _collect_numbers(item, out)
    elif isinstance(value, bool):
        return
    elif isinstance(value, (int, float)):
        number = float(value)
        out.update([number, number / 1000.0, number * 100.0])
    elif isinstance(value, str):
        for token in re.findall(r"\d+(?:[.,]\d+)?", value):
            out.update(_number_candidates(token))


def _validate_numbers(data: InsightData, facts: dict) -> None:
    allowed: set[float] = set()
    _collect_numbers(facts, allowed)
    allowed.update({80.0, 95.0, 90.0, 100.0})
    texts = [data.conclusion, data.headline, data.summary]
    texts.extend(point.text for point in data.points)
    texts.extend(data.actions)
    texts.extend(item.rationale for item in data.recommendations)
    texts.extend(data.limitations)
    texts.append(json.dumps(data.technical_details, ensure_ascii=False))
    for text in texts:
        if not text:
            continue
        for token in re.findall(r"\d+(?:[.,]\d+)?", text):
            candidates = _number_candidates(token)
            if not any(abs(candidate - allowed_value) <= 0.05
                       for candidate in candidates for allowed_value in allowed):
                raise ValueError(f"Ungrounded number in insight: {token}")


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
            hit = InsightResponse.model_validate_json(cached)
            hit.meta["cached"] = True
            return hit
        try:
            data = await self._ollama(facts)
        except Exception as exc:
            logger.warning("Ollama insight gagal (%s: %s); memakai fallback", type(exc).__name__, exc)
            data = fallback(facts)
        response = InsightResponse(data=data, meta={"language": language, "cached": False, "model": self.settings.ollama_model,
                                                     "prompt_version": self.settings.ai_insight_prompt_version,
                                                     "forecast_model_run_id": forecast.meta.get("model_run_id")})
        await self.redis.set(key, response.model_dump_json(), ex=self.settings.ai_insight_cache_ttl_seconds)
        return response

    async def _ollama(self, facts: dict) -> InsightData:
        system = (
            "Return JSON only. Use only supplied facts. Never alter risk_status. "
            "recommendations[].action must be from allowed_actions. "
            "Provide conclusion (one sentence), points (max 3, each with status and text), "
            "actions (2-3 concrete steps in simple Indonesian), and technical_details (object). "
            "Do not invent numbers; use only numbers in the facts. Do not use number ranges."
        )
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
        if result.risk_status != facts.get("derived", {}).get("overall_status"):
            raise ValueError("AI altered risk status")
        if any(point.status not in risk_statuses for point in result.points):
            raise ValueError("Ungrounded point status")
        if any(not set(item.fact_ids).issubset(fact_ids) for item in result.recommendations):
            raise ValueError("Invalid AI citations")
        if not result.conclusion or not result.points or not (2 <= len(result.actions) <= 3):
            raise ValueError("Insight must use the 3-layer format")
        _validate_numbers(result, facts)
        return result.model_copy(update={"source": "ollama"})
