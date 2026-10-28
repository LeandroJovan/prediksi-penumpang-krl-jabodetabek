import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


class Actual(Base):
    __tablename__ = "actuals"
    period: Mapped[date] = mapped_column(Date, primary_key=True)
    value_ribu: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    is_imputed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    source: Mapped[str] = mapped_column(String(64), default="BPS", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Calendar(Base):
    __tablename__ = "calendar"
    period: Mapped[date] = mapped_column(Date, primary_key=True)
    total_hari: Mapped[int] = mapped_column(Integer, nullable=False)
    jumlah_hari_kerja: Mapped[int] = mapped_column(Integer, nullable=False)
    jumlah_libur_nasional_weekday: Mapped[int] = mapped_column(Integer, nullable=False)
    is_lebaran: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_covid: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_actual: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class ModelRun(Base):
    __tablename__ = "model_runs"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    algorithm: Mapped[str] = mapped_column(String(64), nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(16), nullable=False)
    data_start: Mapped[date] = mapped_column(Date, nullable=False)
    data_end: Mapped[date] = mapped_column(Date, nullable=False)
    horizon_max: Mapped[int] = mapped_column(Integer, nullable=False)
    artifact_path: Mapped[str] = mapped_column(Text, nullable=False)
    checksum: Mapped[str] = mapped_column(String(128), nullable=False)
    library_versions: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    model_card: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    trained_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Metric(Base):
    __tablename__ = "metrics"
    __table_args__ = (UniqueConstraint("model_run_id", "subset", "horizon"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("model_runs.id", ondelete="CASCADE"), nullable=False)
    subset: Mapped[str] = mapped_column(String(32), nullable=False)
    horizon: Mapped[int | None] = mapped_column(Integer)
    n: Mapped[int] = mapped_column(Integer, nullable=False)
    mae: Mapped[float | None] = mapped_column(Numeric(14, 4))
    rmse: Mapped[float | None] = mapped_column(Numeric(14, 4))
    mase: Mapped[float | None] = mapped_column(Numeric(14, 4))
    picp80: Mapped[float | None] = mapped_column(Numeric(8, 4))
    picp95: Mapped[float | None] = mapped_column(Numeric(8, 4))
