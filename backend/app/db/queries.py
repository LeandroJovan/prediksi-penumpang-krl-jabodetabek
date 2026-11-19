import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.models import ModelRun

logger = logging.getLogger("krl_backend.db")


async def get_active_model_run(session: AsyncSession) -> ModelRun | None:
    """Model aktif terbaru. Jika data memuat >1 model aktif, pilih yang terbaru dan beri peringatan,
    bukan gagal (``scalar_one_or_none`` melempar error pada kasus itu)."""
    rows = (
        await session.execute(
            select(ModelRun).where(ModelRun.is_active.is_(True)).order_by(ModelRun.trained_at.desc())
        )
    ).scalars().all()
    if len(rows) > 1:
        logger.warning(
            "Ditemukan %d model aktif (%s); memakai yang terbaru: %s",
            len(rows), ", ".join(r.run_id for r in rows), rows[0].run_id,
        )
    return rows[0] if rows else None
