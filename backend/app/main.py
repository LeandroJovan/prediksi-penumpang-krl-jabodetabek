from contextlib import asynccontextmanager
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from backend.app.api.v1.router import api_router
from backend.app.core.cache import InMemoryCache
from backend.app.core.config import REPO_ROOT, get_settings
from backend.app.core.errors import AppError, app_error_handler
from backend.app.core.middleware import request_id_middleware
from backend.app.db.base import Base
from backend.app.db.models import Actual, ModelRun
from backend.app.db.session import SessionLocal, engine
from backend.cli.seed_data import seed_all

logger = logging.getLogger("krl_backend")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    # 1. Connect ke Redis jika URL tersedia
    if settings.redis_url:
        try:
            from redis.asyncio import Redis  # type: ignore

            redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
            await redis_client.ping()
            app.state.redis = redis_client
            logger.info("Connected to Redis cache at %s", settings.redis_url)
        except Exception as exc:
            logger.warning("Redis unavailable (%s); using InMemoryCache fallback", exc)
            app.state.redis = InMemoryCache()
    else:
        app.state.redis = InMemoryCache()

    app.state.session_factory = SessionLocal

    # 2. Inisialisasi skema tabel & auto-seed jika tabel Actual belum terisi
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with SessionLocal() as session:
            count_actual = (await session.execute(select(Actual))).scalars().first()
            if count_actual is None:
                logger.info("Database kosong; menjalankan auto-seed data awal...")
                await seed_all(session=session)
    except Exception as exc:
        logger.warning("DB initialization note: %s", exc)

    yield

    # Shutdown
    if hasattr(app.state, "redis") and hasattr(app.state.redis, "aclose"):
        await app.state.redis.aclose()
    await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

    # Inisialisasi default state agar aman diakses bahkan sebelum event lifespan berjalan
    app.state.redis = InMemoryCache()
    app.state.session_factory = SessionLocal

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )
    app.middleware("http")(request_id_middleware)
    app.add_exception_handler(AppError, app_error_handler)
    app.include_router(api_router, prefix="/api/v1")

    frontend = REPO_ROOT / "frontend"
    if frontend.exists():
        app.mount("/", StaticFiles(directory=str(frontend), html=True), name="frontend")
    return app


app = create_app()
