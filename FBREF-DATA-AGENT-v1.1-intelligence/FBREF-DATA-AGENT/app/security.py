from fastapi import Header, HTTPException
from app.config import settings

def require_admin(x_api_key: str | None = Header(default=None)):
    if settings.admin_api_key and x_api_key != settings.admin_api_key:
        raise HTTPException(status_code=401, detail="Chave administrativa inválida ou ausente.")
