"""maksimal satu model aktif (partial unique index)

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-19
"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

INDEX = "uq_model_runs_single_active"


def upgrade() -> None:
    bind = op.get_bind()
    active = bind.execute(sa.text("SELECT COUNT(*) FROM model_runs WHERE is_active")).scalar()
    if active and active > 1:
        raise RuntimeError(
            f"Ditemukan {active} model aktif di model_runs. Sisakan satu saja "
            "(UPDATE model_runs SET is_active = false WHERE run_id <> '<yang dipertahankan>') lalu ulangi."
        )
    with op.batch_alter_table("model_runs") as batch_op:
        batch_op.create_index(
            INDEX,
            ["is_active"],
            unique=True,
            postgresql_where=sa.text("is_active"),
            sqlite_where=sa.text("is_active"),
        )


def downgrade() -> None:
    with op.batch_alter_table("model_runs") as batch_op:
        batch_op.drop_index(
            INDEX,
            postgresql_where=sa.text("is_active"),
            sqlite_where=sa.text("is_active"),
        )
