import secrets

from fastapi import Header, HTTPException, status

from backend.app.core.config import get_settings


async def require_admin_api_key(x_api_key: str | None = Header(default=None)) -> None:
    expected = get_settings().krl_api_key
    if not expected or not x_api_key or not secrets.compare_digest(expected, x_api_key):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
