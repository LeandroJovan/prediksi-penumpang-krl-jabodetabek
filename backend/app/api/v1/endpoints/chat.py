from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import db_session, redis_client, settings
from backend.app.core.config import Settings
from backend.app.core.security import rate_limit
from backend.app.schemas.chat import ChatRequest, ChatResponse
from backend.app.services.chat import ChatService

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse, dependencies=[Depends(rate_limit)])
async def chat(
    payload: ChatRequest,
    session: AsyncSession = Depends(db_session),
    app_settings: Settings = Depends(settings),
    redis=Depends(redis_client),
) -> ChatResponse:
    """Tanya jawab seputar prakiraan, risiko kapasitas, skenario kapasitas, dan pola musiman.

    Jawaban berupa teks polos yang berbasis fakta data; tidak ada HTML dari server.
    """
    return await ChatService(session, app_settings, redis).reply(payload)
