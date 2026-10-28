from fastapi import APIRouter

from backend.app.api.v1.endpoints import forecasts, health, insights, meta, metrics, models, passengers, risk

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(meta.router)
api_router.include_router(passengers.router)
api_router.include_router(forecasts.router)
api_router.include_router(models.router)
api_router.include_router(metrics.router)
api_router.include_router(risk.router)
api_router.include_router(insights.router)
