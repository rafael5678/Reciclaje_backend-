from fastapi import APIRouter, Header

from app.models.schemas import LoginIn, RegisterIn, TokenOut, UserOut
from app.services.auth_service import auth_service, public_user
from app.views.deps import CurrentUser

router = APIRouter(tags=["auth"])


def _bearer(authorization: str | None) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()
    return None


@router.post("/auth/register", response_model=TokenOut)
def register(body: RegisterIn, authorization: str | None = Header(default=None)) -> dict:
    return auth_service.register(body.name, body.email, body.password, _bearer(authorization))


@router.post("/auth/login", response_model=TokenOut)
def login(body: LoginIn, authorization: str | None = Header(default=None)) -> dict:
    return auth_service.login(body.email, body.password, _bearer(authorization))


@router.post("/auth/guest", response_model=TokenOut)
def guest() -> dict:
    return auth_service.guest()


@router.get("/auth/me", response_model=UserOut)
def me(user: dict = CurrentUser) -> dict:
    return public_user(user)
