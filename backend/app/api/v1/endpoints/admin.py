import logging
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import db_session, redis_client, settings
from backend.app.core.config import Settings
from backend.app.core.errors import AppError
from backend.app.core.pipeline_data import data_bounds
from backend.app.core.security import admin_key_is_usable, rate_limit, require_admin_api_key
from backend.app.db.models import Actual, Metric, ModelRun
from backend.app.db.queries import get_active_model_run
from backend.cli.seed_data import seed_all

logger = logging.getLogger("krl_backend.admin")

# Semua endpoint admin: dibatasi laju + wajib X-API-Key (fail-closed bila kunci belum diatur).
router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(rate_limit), Depends(require_admin_api_key)],
)

CACHE_PREFIXES = ("forecast:", "insight:")


def _audit(request: Request, action: str, **details) -> None:
    """Catatan audit aksi admin (tanpa kunci API). request_id berasal dari middleware."""
    logger.info(
        "ADMIN action=%s request_id=%s ip=%s %s",
        action,
        getattr(request.state, "request_id", None),
        request.client.host if request.client else "unknown",
        " ".join(f"{k}={v}" for k, v in details.items()),
    )


async def clear_cache(cache) -> int:
    """Hapus kunci forecast & insight saja (bukan seluruh Redis, yang mungkin dipakai layanan lain)."""
    removed = 0
    for prefix in CACHE_PREFIXES:
        if hasattr(cache, "delete_prefix"):
            removed += await cache.delete_prefix(prefix)
        else:
            async for key in cache.scan_iter(match=f"{prefix}*", count=500):
                await cache.delete(key)
                removed += 1
    return removed


def _has_loadable_artifact(artifact_path: str, artifacts_dir: Path) -> bool:
    folder = Path(artifact_path).resolve()
    return (
        folder.is_relative_to(artifacts_dir.resolve())
        and (folder / "model.pkl").is_file()
        and (folder / "manifest.json").is_file()
    )


@router.get("/status")
async def admin_status(
    session: AsyncSession = Depends(db_session),
    app_settings: Settings = Depends(settings),
    cache=Depends(redis_client),
) -> dict:
    """Ringkasan kondisi sistem. Tidak pernah memuat nilai rahasia (hanya status terkonfigurasi atau tidak)."""
    try:
        cache_ok = bool(await cache.ping())
    except Exception:
        logger.exception("Admin status: cache tidak dapat dijangkau")
        cache_ok = False

    active = await get_active_model_run(session)
    n_actuals = (await session.execute(select(func.count()).select_from(Actual))).scalar_one()
    n_runs = (await session.execute(select(func.count()).select_from(ModelRun))).scalar_one()
    n_metrics = (await session.execute(select(func.count()).select_from(Metric))).scalar_one()
    start, end = data_bounds()
    return {
        "data": {
            "app_env": app_settings.app_env,
            "cache": {"backend": type(cache).__name__, "reachable": cache_ok},
            "active_model": active.run_id if active else None,
            "counts": {"actuals": n_actuals, "model_runs": n_runs, "metrics": n_metrics},
            "data_range": {
                "start": start.isoformat() if start else None,
                "end": end.isoformat() if end else None,
            },
            "security": {
                "admin_key_configured": admin_key_is_usable(app_settings.krl_api_key),
                "model_signing_enabled": bool(app_settings.model_signing_key),
                "rate_limit_per_minute": app_settings.rate_limit_per_minute,
            },
        }
    }


@router.post("/cache/clear")
async def admin_clear_cache(request: Request, cache=Depends(redis_client)) -> dict:
    """Bersihkan cache forecast & insight (mis. setelah data atau konfigurasi kapasitas berubah)."""
    removed = await clear_cache(cache)
    _audit(request, "cache.clear", removed=removed)
    return {"data": {"cleared": removed}}


@router.post("/seed")
async def admin_seed(
    request: Request,
    session: AsyncSession = Depends(db_session),
    cache=Depends(redis_client),
) -> dict:
    """Jalankan ulang seed (idempoten) dari CSV pipeline terbaru, lalu bersihkan cache turunan."""
    try:
        await seed_all(session=session)
    except RuntimeError as exc:
        logger.exception("Admin seed gagal")
        raise AppError("SEED_FAILED", 503, "Seed gagal: data pipeline tidak lengkap.") from exc
    removed = await clear_cache(cache)
    _audit(request, "seed", cache_cleared=removed)
    return {"data": {"seeded": True, "cache_cleared": removed}}


@router.post("/activate-model/{run_id}")
async def admin_activate_model(
    run_id: str,
    request: Request,
    session: AsyncSession = Depends(db_session),
    app_settings: Settings = Depends(settings),
    cache=Depends(redis_client),
) -> dict:
    """Jadikan ``run_id`` satu-satunya model aktif.

    Hanya model dengan artifact (model.pkl + manifest.json) di bawah ARTIFACTS_DIR yang boleh diaktifkan.
    Model "precomputed" (berbasis CSV) tidak punya bundle, sehingga mengaktifkannya hanya akan memberi
    label model yang salah pada prakiraan CSV.
    """
    target = (await session.execute(select(ModelRun).where(ModelRun.run_id == run_id))).scalar_one_or_none()
    if target is None:
        raise AppError("MODEL_NOT_FOUND", 404, "Model run not found.")
    if target.is_active:
        return {"data": {"run_id": run_id, "is_active": True, "changed": False}}
    if not _has_loadable_artifact(target.artifact_path, app_settings.artifacts_dir):
        raise AppError(
            "MODEL_NOT_ACTIVATABLE",
            409,
            "Model has no loadable artifact (model.pkl + manifest.json under ARTIFACTS_DIR).",
        )

    # Satu transaksi: nonaktifkan yang lama dulu agar partial unique index tidak terlanggar.
    previous = await get_active_model_run(session)
    await session.execute(update(ModelRun).where(ModelRun.is_active.is_(True)).values(is_active=False))
    target.is_active = True
    await session.commit()

    removed = await clear_cache(cache)
    _audit(
        request,
        "model.activate",
        run_id=run_id,
        previous=previous.run_id if previous else None,
        cache_cleared=removed,
    )
    return {"data": {"run_id": run_id, "is_active": True, "changed": True, "cache_cleared": removed}}
