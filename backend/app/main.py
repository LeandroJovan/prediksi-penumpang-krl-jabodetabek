from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from redis.asyncio import Redis

from backend.app.api.v1.router import api_router
from backend.app.core.config import get_settings
from backend.app.core.errors import AppError, app_error_handler
from backend.app.core.middleware import request_id_middleware
from backend.app.db.models import ModelRun
from backend.app.db.session import SessionLocal, engine
from backend.app.ml.loader import load_bundle
from sqlalchemy import select


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.redis = Redis.from_url(settings.redis_url, decode_responses=True)
    app.state.session_factory = SessionLocal
    # Best effort only: an empty database is valid before the first model import.
    try:
        async with SessionLocal() as session:
            active = (await session.execute(select(ModelRun).where(ModelRun.is_active.is_(True)))).scalar_one_or_none()
            if active is not None:
                load_bundle(active.artifact_path)
    except Exception:
        pass
    yield
    await app.state.redis.aclose()
    await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=False,
                       allow_methods=["GET", "POST"], allow_headers=["*"])
    app.middleware("http")(request_id_middleware)
    app.add_exception_handler(AppError, app_error_handler)
    app.include_router(api_router, prefix="/api/v1")
    frontend = Path("frontend")
    if frontend.exists():
        app.mount("/", StaticFiles(directory=frontend, html=True), name="frontend")
    return app


app = create_app()
