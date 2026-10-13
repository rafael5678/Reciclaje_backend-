from datetime import datetime

from app.repositories.user_repository import UserRepository
from app.services.security import hash_password

user_repository = UserRepository()


def seed_if_empty() -> None:
    if user_repository.get_by_email("rafael@ecoscan.app") is not None:
        return
    created = datetime.now().astimezone().isoformat(timespec="seconds")
    user_repository.create(
        "Rafael Gonzalez",
        "rafael@ecoscan.app",
        hash_password("ecoscan123"),
        created,
    )
