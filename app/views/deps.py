from fastapi import Depends, Header, HTTPException

from app.services.auth_service import auth_service


def bearer_token(authorization: str | None) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()
    return None


def current_user(authorization: str | None = Header(default=None)) -> dict:
    token = bearer_token(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Inicia sesión para continuar")
    user = auth_service.user_from_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="La sesión expiró. Entra de nuevo")
    return user


CurrentUser = Depends(current_user)
