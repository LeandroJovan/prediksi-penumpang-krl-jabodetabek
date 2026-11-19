from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import db_session, redis_client, settings
from backend.app.core.config import Settings
from backend.app.services.dashboard import DashboardService

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard")
@router.get("/data", include_in_schema=False)  # alias lama
async def dashboard_bundle(
    ambang_kapasitas: float | None = Query(default=None, gt=0, le=1_000_000, allow_inf_nan=False),
    session: AsyncSession = Depends(db_session),
    app_settings: Settings = Depends(settings),
    redis=Depends(redis_client),
) -> dict:
    """Bundle JSON dashboard: prakiraan dari model aktif backend (fallback CSV pipeline)."""
    return await DashboardService(session, app_settings, redis).bundle(ambang_kapasitas)
