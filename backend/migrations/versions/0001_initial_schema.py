"""baseline: skema awal (setara hasil create_all lama, tanpa index model aktif)

Revision ID: 0001
Revises: 
Create Date: 2026-11-19 14:06:15.688166
"""
import sqlalchemy as sa
from alembic import op

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('actuals',
    sa.Column('period', sa.Date(), nullable=False),
    sa.Column('value_ribu', sa.Numeric(precision=14, scale=2), nullable=False),
    sa.Column('is_imputed', sa.Boolean(), nullable=False),
    sa.Column('source', sa.String(length=64), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.PrimaryKeyConstraint('period')
    )
    op.create_table('calendar',
    sa.Column('period', sa.Date(), nullable=False),
    sa.Column('total_hari', sa.Integer(), nullable=False),
    sa.Column('jumlah_hari_kerja', sa.Integer(), nullable=False),
    sa.Column('jumlah_libur_nasional_weekday', sa.Integer(), nullable=False),
    sa.Column('is_lebaran', sa.Boolean(), nullable=False),
    sa.Column('is_covid', sa.Boolean(), nullable=False),
    sa.Column('is_actual', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('period')
    )
    op.create_table('model_runs',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('run_id', sa.String(length=128), nullable=False),
    sa.Column('algorithm', sa.String(length=64), nullable=False),
    sa.Column('model_version', sa.String(length=64), nullable=False),
    sa.Column('schema_version', sa.String(length=16), nullable=False),
    sa.Column('data_start', sa.Date(), nullable=False),
    sa.Column('data_end', sa.Date(), nullable=False),
    sa.Column('horizon_max', sa.Integer(), nullable=False),
    sa.Column('artifact_path', sa.Text(), nullable=False),
    sa.Column('checksum', sa.String(length=128), nullable=False),
    sa.Column('library_versions', sa.JSON(), nullable=False),
    sa.Column('model_card', sa.JSON(), nullable=False),
    sa.Column('trained_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('run_id')
    )
    op.create_table('metrics',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('model_run_id', sa.Uuid(), nullable=False),
    sa.Column('subset', sa.String(length=32), nullable=False),
    sa.Column('horizon', sa.Integer(), nullable=True),
    sa.Column('n', sa.Integer(), nullable=False),
    sa.Column('mae', sa.Numeric(precision=14, scale=4), nullable=True),
    sa.Column('rmse', sa.Numeric(precision=14, scale=4), nullable=True),
    sa.Column('mase', sa.Numeric(precision=14, scale=4), nullable=True),
    sa.Column('picp80', sa.Numeric(precision=8, scale=4), nullable=True),
    sa.Column('picp95', sa.Numeric(precision=8, scale=4), nullable=True),
    sa.ForeignKeyConstraint(['model_run_id'], ['model_runs.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('model_run_id', 'subset', 'horizon')
    )


def downgrade() -> None:
    op.drop_table('metrics')
    op.drop_table('model_runs')
    op.drop_table('calendar')
    op.drop_table('actuals')
