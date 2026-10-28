from backend.app.core.config import Settings
from backend.app.services.risk import calculate_risk


def settings(**values) -> Settings:
    return Settings(database_url="postgresql+asyncpg://x", redis_url="redis://x", **values)


def test_capacity_split_returns_warning() -> None:
    result = calculate_risk(10_000, {"total_hari": 30, "jumlah_hari_kerja": 20}, settings(
        krl_capacity_weekday_ribu=400, krl_capacity_weekend_ribu=250
    ))
    assert result.status == "waspada"
    assert result.capacity_ribu == 10_500


def test_missing_capacity_is_explicit() -> None:
    result = calculate_risk(10_000, {"total_hari": 30, "jumlah_hari_kerja": 20}, settings())
    assert result.status == "belum_ditentukan"
