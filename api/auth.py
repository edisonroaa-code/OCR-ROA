"""
ROA OCR — Middleware de autenticación por API Key
"""
from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader
from config import settings

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(api_key: str = Security(API_KEY_HEADER)) -> str:
    """
    Dependencia FastAPI que valida el API Key.
    
    Uso:
        @router.get("/endpoint")
        async def endpoint(key: str = Depends(require_api_key)):
            ...
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key requerida. Usa el header: X-API-Key: <tu-key>",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    if api_key not in settings.api_keys_list:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API Key inválida o no autorizada",
        )

    return api_key
