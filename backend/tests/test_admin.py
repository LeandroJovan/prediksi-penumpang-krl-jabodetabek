import hashlib
import json
import uuid
from datetime import date, datetime, timezone

import joblib
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.app.api.deps import db_session
from backend.app.core import security
from backend.app.core.cache import InMemoryCache
from backend.app.core.config import get_settings
from backend.app.db.base import Base
from backend.app.db.models import ModelRun
from backend.app.main import app
from backend.cli.seed_data import seed_all
from backend.tests.fake_bundle import FakeBundle

KEY = "kunci-admin-yang-cukup-panjang-123"
HEADERS = {"X-API-Key": KEY}


@pytest.fixture
async def env(tmp_path, monkeypatch):
    """DB sementara + cache baru + kunci admin valid, terisolasi dari DB bersama test lain."""
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'admin.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override():
        async with factory() as session:
            yield session

    app.dependency_overrides[db_session] = override
    original_cache = app.state.redis
    app.state.redis = InMemoryCache()
    settings = get_settings()
    monkeypatch.setattr(settings, "krl_api_key", KEY)
    monkeypatch.setattr(settings, "artifacts_dir", tmp_path / "artifacts")
    monkeypatch.setattr(settings, "rate_limit_per_minute", 1000)
    security._limiter._hits.clear()
    security._auth_failures._hits.clear()
    try:
        yield factory
    finally:
        app.dependency_overrides.pop(db_session, None)
        app.state.redis = original_cache
        security._limiter._hits.clear()
        security._auth_failures._hits.clear()
        await engine.dispose()


@pytest.fixture
async def client(env):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


def _make_artifact(folder, run_id):
    folder.mkdir(parents=True)
    model = folder / "model.pkl"
    joblib.dump(FakeBundle(), model)
    digest = hashlib.sha256(model.read_bytes()).hexdigest()
    (folder / "manifest.json").write_text(
        json.dumps({"run_id": run_id, "horizon_max": 6, "files": {"model.pkl": {"sha256": f"sha256:{digest}"}}}),
        encoding="utf-8",
    )


# ------------------------------------------------------------------ autentikasi
@pytest.mark.parametrize("key", [None, "", "pendek", "replace-with-a-long-random-secret", "CHANGE-ME"])
async def test_admin_disabled_when_key_missing_weak_or_placeholder(client, monkeypatch, key):
    monkeypatch.setattr(get_settings(), "krl_api_key", key)
    res = await client.get("/api/v1/admin/status", headers={"X-API-Key": key or "x"})
    assert res.status_code == 503
    # Bahkan header yang sama dengan placeholder tidak boleh membuka akses.
    assert "disabled" in res.json()["detail"]


async def test_admin_rejects_missing_and_wrong_key(client):
    assert (await client.get("/api/v1/admin/status")).status_code == 401
    wrong = await client.get("/api/v1/admin/status", headers={"X-API-Key": "salah-" + KEY})
    assert wrong.status_code == 401
    assert wrong.headers["WWW-Authenticate"] == "ApiKey"


async def test_admin_accepts_correct_key(client):
    assert (await client.get("/api/v1/admin/status", headers=HEADERS)).status_code == 200


async def test_admin_key_in_query_string_is_not_accepted(client):
    assert (await client.get(f"/api/v1/admin/status?x_api_key={KEY}")).status_code == 401


async def test_admin_brute_force_is_locked_out_even_for_correct_key(client):
    for _ in range(10):
        assert (await client.get("/api/v1/admin/status", headers={"X-API-Key": "tebakan"})).status_code == 401
    locked = await client.get("/api/v1/admin/status", headers=HEADERS)
    assert locked.status_code == 429
    assert int(locked.headers["Retry-After"]) >= 1


async def test_every_admin_route_requires_auth(client):
    for method, path in [
        ("GET", "/api/v1/admin/status"),
        ("POST", "/api/v1/admin/cache/clear"),
        ("POST", "/api/v1/admin/seed"),
        ("POST", "/api/v1/admin/activate-model/x"),
    ]:
        res = await client.request(method, path)
        assert res.status_code == 401, (method, path)


# ------------------------------------------------------------------ status
async def test_status_reports_state_without_leaking_secrets(client, env):
    async with env() as session:
        await seed_all(session=session)
    res = await client.get("/api/v1/admin/status", headers=HEADERS)
    body = res.json()["data"]
    assert body["active_model"] == "lgbm_cqr_v1"
    assert body["counts"]["model_runs"] == 2
    assert body["cache"] == {"backend": "InMemoryCache", "reachable": True}
    assert body["security"]["admin_key_configured"] is True
    assert KEY not in res.text


# ------------------------------------------------------------------ cache
async def test_cache_clear_removes_only_app_prefixes(client):
    cache = app.state.redis
    await cache.set("forecast:v1:a", "1")
    await cache.set("insight:v1:b", "2")
    await cache.set("layanan-lain:c", "3")
    res = await client.post("/api/v1/admin/cache/clear", headers=HEADERS)
    assert res.json()["data"]["cleared"] == 2
    assert await cache.get("forecast:v1:a") is None
    assert await cache.get("insight:v1:b") is None
    assert await cache.get("layanan-lain:c") == "3"


async def test_cache_clear_supports_redis_style_scan(client):
    class FakeRedis:
        def __init__(self):
            self.data = {"forecast:1": "x", "insight:2": "y", "other": "z"}

        async def scan_iter(self, match, count):
            prefix = match.rstrip("*")
            for key in [k for k in self.data if k.startswith(prefix)]:
                yield key

        async def delete(self, key):
            self.data.pop(key, None)

        async def ping(self):
            return True

    fake = FakeRedis()
    app.state.redis = fake
    res = await client.post("/api/v1/admin/cache/clear", headers=HEADERS)
    assert res.json()["data"]["cleared"] == 2
    assert fake.data == {"other": "z"}


# ------------------------------------------------------------------ seed
async def test_seed_endpoint_populates_empty_db_and_is_idempotent(client, env):
    first = await client.post("/api/v1/admin/seed", headers=HEADERS)
    second = await client.post("/api/v1/admin/seed", headers=HEADERS)
    assert first.status_code == second.status_code == 200
    async with env() as session:
        runs = (await session.execute(select(ModelRun))).scalars().all()
    assert sorted(r.run_id for r in runs) == ["lgbm_cqr_v1", "sarimax_v1"]
    assert sum(r.is_active for r in runs) == 1


# ------------------------------------------------------------------ activate model
async def _add_run(factory, run_id, artifact_path, active=False):
    async with factory() as session:
        session.add(
            ModelRun(
                id=uuid.uuid4(), run_id=run_id, algorithm="x", model_version="1", schema_version="1",
                data_start=date(2020, 1, 1), data_end=date(2021, 1, 1), horizon_max=6,
                artifact_path=str(artifact_path), checksum="c", library_versions={}, model_card={},
                trained_at=datetime.now(timezone.utc), is_active=active,
            )
        )
        await session.commit()


async def _active_ids(factory):
    async with factory() as session:
        rows = (await session.execute(select(ModelRun).where(ModelRun.is_active.is_(True)))).scalars().all()
    return [r.run_id for r in rows]


async def test_activate_unknown_model_is_404(client):
    res = await client.post("/api/v1/admin/activate-model/tidak-ada", headers=HEADERS)
    assert res.status_code == 404


async def test_activate_model_without_artifact_is_refused(client, env):
    async with env() as session:
        await seed_all(session=session)
    res = await client.post("/api/v1/admin/activate-model/sarimax_v1", headers=HEADERS)
    assert res.status_code == 409
    assert await _active_ids(env) == ["lgbm_cqr_v1"]  # tidak berubah


async def test_activate_model_with_artifact_switches_single_active_and_clears_cache(client, env, tmp_path):
    async with env() as session:
        await seed_all(session=session)
    folder = tmp_path / "artifacts" / "real_v1"
    _make_artifact(folder, "real_v1")
    await _add_run(env, "real_v1", folder)
    await app.state.redis.set("forecast:v1:lama", "x")

    res = await client.post("/api/v1/admin/activate-model/real_v1", headers=HEADERS)
    assert res.status_code == 200
    assert res.json()["data"]["changed"] is True
    assert await _active_ids(env) == ["real_v1"]
    assert await app.state.redis.get("forecast:v1:lama") is None

    again = await client.post("/api/v1/admin/activate-model/real_v1", headers=HEADERS)
    assert again.json()["data"]["changed"] is False


async def test_activate_refuses_artifact_outside_artifacts_dir(client, env, tmp_path):
    outside = tmp_path / "di-luar" / "m"
    _make_artifact(outside, "luar")
    await _add_run(env, "luar", outside)
    res = await client.post("/api/v1/admin/activate-model/luar", headers=HEADERS)
    assert res.status_code == 409


async def test_admin_actions_are_audited_without_key(client, caplog):
    with caplog.at_level("INFO", logger="krl_backend.admin"):
        await client.post("/api/v1/admin/cache/clear", headers={**HEADERS, "X-Request-ID": "req-audit-1"})
    text = caplog.text
    assert "ADMIN action=cache.clear" in text and "req-audit-1" in text
    assert KEY not in text
