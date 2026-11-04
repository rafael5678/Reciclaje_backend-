"""Register, login, guest, and profile routes."""
from fastapi import APIRouter, Header

from app.models.schemas import LoginIn, RegisterIn, TokenOut, UserOut
from app.services.auth_service import auth_service, public_user
from app.views.deps import CurrentUser, bearer_token

router = APIRouter(tags=["auth"])


@router.post("/auth/register", response_model=TokenOut)
def register(body: RegisterIn, authorization: str | None = Header(default=None)) -> dict:
    """Create an account and optional guest merge."""
    return auth_service.register(body.name, body.email, body.password, bearer_token(authorization))


@router.post("/auth/login", response_model=TokenOut)
def login(body: LoginIn, authorization: str | None = Header(default=None)) -> dict:
    """Authenticate and optional guest merge."""
    return auth_service.login(body.email, body.password, bearer_token(authorization))


@router.post("/auth/guest", response_model=TokenOut)
def guest() -> dict:
    return auth_service.guest()


@router.get("/auth/me", response_model=UserOut)
def me(user: dict = CurrentUser) -> dict:
    return public_user(user)
