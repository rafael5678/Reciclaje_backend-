from fastapi import Depends, Header, HTTPException

from app.services.auth_service import auth_service


def current_user(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Inicia sesión para continuar")
    token = authorization.split(" ", 1)[1].strip()
    user = auth_service.user_from_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="La sesión expiró. Entra de nuevo")
    return user


CurrentUser = Depends(current_user)
