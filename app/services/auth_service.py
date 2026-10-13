from datetime import datetime

from fastapi import HTTPException

from app.repositories.user_repository import UserRepository
from app.services.security import hash_password, make_token, read_token, verify_password

user_repository = UserRepository()


class AuthService:
    def register(self, name: str, email: str, password: str) -> dict:
        email = email.lower().strip()
        if "@" not in email or "." not in email.split("@")[-1]:
            raise HTTPException(status_code=400, detail="Escribe un correo válido")
        if user_repository.get_by_email(email):
            raise HTTPException(status_code=409, detail="Ese correo ya tiene una cuenta")
        created = datetime.now().astimezone().isoformat(timespec="seconds")
        user = user_repository.create(name, email, hash_password(password), created)
        return self._session(user)

    def login(self, email: str, password: str) -> dict:
        user = user_repository.get_by_email(email)
        if user is None or not verify_password(password, user["password_hash"]):
            raise HTTPException(status_code=401, detail="Correo o contraseña incorrectos")
        return self._session(user)

    def user_from_token(self, token: str) -> dict | None:
        user_id = read_token(token)
        if user_id is None:
            return None
        return user_repository.get_by_id(user_id)

    def _session(self, user: dict) -> dict:
        return {
            "token": make_token(user["id"]),
            "user": {"id": user["id"], "name": user["name"], "email": user["email"]},
        }


auth_service = AuthService()
