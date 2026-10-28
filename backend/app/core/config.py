from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "KRL Forecast API"
    app_env: str = "development"
    database_url: str
    redis_url: str
    cors_origins: str = ""
    krl_api_key: str | None = None
    artifacts_dir: Path = Path("artifacts/models")
    forecast_cache_ttl_seconds: int = Field(default=3600, ge=1)
    inference_timeout_seconds: int = Field(default=15, ge=1)
    krl_capacity_weekday_ribu: float | None = Field(default=None, gt=0)
    krl_capacity_weekend_ribu: float | None = Field(default=None, gt=0)
    krl_risk_waspada_ratio: float = Field(default=0.90, gt=0, lt=1)
    ollama_base_url: str = "http://ollama:11434"
    ollama_model: str = "qwen3.5:4b"
    ollama_timeout_seconds: int = Field(default=12, ge=1)
    ollama_max_concurrency: int = Field(default=1, ge=1)
    ai_insight_cache_ttl_seconds: int = Field(default=86400, ge=1)
    ai_insight_max_output_chars: int = Field(default=500, ge=100, le=2000)
    ai_insight_prompt_version: str = "1.0"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
