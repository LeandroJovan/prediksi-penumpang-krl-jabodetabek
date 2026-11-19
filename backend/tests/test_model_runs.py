import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.app.db.base import Base
from backend.app.db.models import ModelRun
from backend.app.db.queries import get_active_model_run
from backend.app.main import startup_lock


def _run(run_id, active, age_days=0):
    return ModelRun(
        id=uuid.uuid4(), run_id=run_id, algorithm="x", model_version="1", schema_version="1",
        data_start=date(2020, 1, 1), data_end=date(2021, 1, 1), horizon_max=6,
        artifact_path="p", checksum="c", library_versions={}, model_card={},
        trained_at=datetime.now(timezone.utc) - timedelta(days=age_days), is_active=active,
    )


@pytest.fixture
async def factory(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 't.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


async def test_db_rejects_second_active_model(factory):
    async with factory() as s:
        s.add(_run("a", True))
        await s.commit()
        s.add(_run("b", True))
        with pytest.raises(IntegrityError):
            await s.commit()


async def test_multiple_inactive_models_allowed(factory):
    async with factory() as s:
        s.add_all([_run("a", False), _run("b", False), _run("c", True)])
        await s.commit()
        assert (await get_active_model_run(s)).run_id == "c"


async def test_get_active_model_run_tolerates_legacy_duplicates(tmp_path, caplog):
    # DB lama tanpa index: simulasikan dengan membuat tabel lalu menghapus index.
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'legacy.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.exec_driver_sql("DROP INDEX uq_model_runs_single_active")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        s.add_all([_run("old", True, age_days=10), _run("new", True, age_days=1)])
        await s.commit()
        with caplog.at_level("WARNING"):
            active = await get_active_model_run(s)
    assert active.run_id == "new"
    assert "2 model aktif" in caplog.text
    await engine.dispose()


async def test_get_active_model_run_none_when_empty(factory):
    async with factory() as s:
        assert await get_active_model_run(s) is None


async def test_startup_lock_is_noop_on_sqlite(factory):
    engine = factory.kw["bind"]
    async with startup_lock(engine):
        pass
