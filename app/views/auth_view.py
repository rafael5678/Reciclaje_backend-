from fastapi import APIRouter

from app.models.schemas import LoginIn, RegisterIn, TokenOut, UserOut
from app.services.auth_service import auth_service
from app.views.deps import CurrentUser

router = APIRouter(tags=["auth"])


@router.post("/auth/register", response_model=TokenOut)
def register(body: RegisterIn) -> dict:
    return auth_service.register(body.name, body.email, body.password)


@router.post("/auth/login", response_model=TokenOut)
def login(body: LoginIn) -> dict:
    return auth_service.login(body.email, body.password)


@router.get("/auth/me", response_model=UserOut)
def me(user: dict = CurrentUser) -> dict:
    return {"id": user["id"], "name": user["name"], "email": user["email"]}
