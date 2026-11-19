from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from backend.app.core.config import get_settings

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


@pytest.fixture
def alembic_cfg(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "database_url", f"sqlite+aiosqlite:///{tmp_path / 'm.db'}")
    return Config(str(ALEMBIC_INI))


def test_migrations_upgrade_and_match_models(alembic_cfg):
    command.upgrade(alembic_cfg, "head")
    # Gagal jika model SQLAlchemy berubah tanpa revisi migrasi yang menyertainya.
    command.check(alembic_cfg)


def test_migrations_are_reversible(alembic_cfg):
    command.upgrade(alembic_cfg, "head")
    command.downgrade(alembic_cfg, "base")
    command.upgrade(alembic_cfg, "head")
