from typing import Literal

from pydantic import BaseModel, Field


class Recommendation(BaseModel):
    action: Literal[
        "monitor_capacity",
        "review_operational_readiness",
        "prepare_contingency_plan",
        "review_capacity_assumption",
    ]
    priority: Literal["low", "medium", "high"]
    rationale: str = Field(max_length=500)
    fact_ids: list[str]


class InsightData(BaseModel):
    risk_status: Literal["aman", "waspada", "kritis", "belum_ditentukan"]
    headline: str = Field(max_length=500)
    summary: str = Field(max_length=500)
    recommendations: list[Recommendation] = Field(max_length=3)
    limitations: list[str] = Field(default_factory=list, max_length=3)
    fact_ids: list[str]
    source: Literal["ollama", "fallback"] = "ollama"


class InsightResponse(BaseModel):
    data: InsightData
    meta: dict
