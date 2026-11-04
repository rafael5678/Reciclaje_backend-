"""Classrooms, HMAC rotating invite, and ranking trees."""
import hashlib
import hmac
import secrets
import time
from datetime import datetime, timedelta

from fastapi import HTTPException

from app.models.schemas import ClassroomOut, InviteOut, RankingOut, RankingRow
from app.repositories.classroom_repository import ClassroomRepository
from app.services.auth_service import is_guest
from app.services.security import SECRET

classroom_repository = ClassroomRepository()
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
MAX_CLASSROOMS = 10
INVITE_PERIOD = 30


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _window(now: float | None = None) -> int:
    return int((now if now is not None else time.time()) // INVITE_PERIOD)


def live_code(row: dict, window: int | None = None) -> str:
    stamp = window if window is not None else _window()
    digest = hmac.new(SECRET, f"{row['id']}|{row['code']}|{stamp}".encode("utf-8"), hashlib.sha256).hexdigest()
    return "".join(CODE_ALPHABET[int(digest[index : index + 2], 16) % len(CODE_ALPHABET)] for index in range(0, 12, 2))


def _expires_in() -> int:
    leftover = INVITE_PERIOD - int(time.time() % INVITE_PERIOD)
    return leftover if leftover > 0 else INVITE_PERIOD


def _tree(points: int, top_code: str | None) -> tuple[str, int]:
    code = (top_code or "").upper()
    if code in {"PET", "HDPE", "MLT"}:
        kind = "palmera"
    elif code == "ORG":
        kind = "frutal"
    elif code == "PAP":
        kind = "pino"
    elif code in {"VID", "MET"}:
        kind = "roble"
    else:
        kind = "ceiba"
    if points >= 400:
        stage = 5
    elif points >= 200:
        stage = 4
    elif points >= 100:
        stage = 3
    elif points >= 50:
        stage = 2
    elif points >= 20:
        stage = 1
    else:
        stage = 0
    return kind, stage


def _present(row: dict, user_id: int, members: int | None = None) -> ClassroomOut:
    return ClassroomOut(
        id=row["id"],
        name=row["name"],
        code=live_code(row),
        members=int(members if members is not None else row.get("members", 0)),
        is_owner=int(row["owner_id"]) == user_id,
        invite_expires_in=_expires_in(),
    )


class ClassroomService:
    def list_for(self, user: dict) -> list[ClassroomOut]:
        """List scans or classrooms for a user."""
        return [_present(row, user["id"]) for row in classroom_repository.for_user(user["id"])]

    def create(self, user: dict, name: str) -> ClassroomOut:
        """Insert a new row and return it."""
        self._require_account(user)
        if len(classroom_repository.for_user(user["id"])) >= MAX_CLASSROOMS:
            raise HTTPException(status_code=400, detail=f"Puedes estar en máximo {MAX_CLASSROOMS} salones")
        for _ in range(5):
            code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(6))
            if classroom_repository.by_code(code) is None:
                row = classroom_repository.create(name, code, user["id"], _now())
                return _present(row, user["id"], members=1)
        raise HTTPException(status_code=500, detail="No pude generar un código. Intenta otra vez")

    def invite(self, user: dict, classroom_id: int) -> InviteOut:
        """Return the live rotating invite code."""
        row = self._member_room(user, classroom_id)
        return InviteOut(code=live_code(row), expires_in=_expires_in(), period=INVITE_PERIOD)

    def join(self, user: dict, code: str) -> ClassroomOut:
        """Join a classroom with a live or previous code."""
        self._require_account(user)
        needle = code.strip().upper()
        window = _window()
        row = None
        for candidate in classroom_repository.all():
            if live_code(candidate, window) == needle or live_code(candidate, window - 1) == needle:
                row = candidate
                break
        if row is None:
            raise HTTPException(status_code=404, detail="Ese código ya no vale o no existe. Pide el código nuevo al dueño del salón.")
        if not classroom_repository.is_member(row["id"], user["id"]):
            if len(classroom_repository.for_user(user["id"])) >= MAX_CLASSROOMS:
                raise HTTPException(status_code=400, detail=f"Puedes estar en máximo {MAX_CLASSROOMS} salones")
            classroom_repository.add_member(row["id"], user["id"], _now())
        return _present(row, user["id"], members=classroom_repository.count_members(row["id"]))

    def leave(self, user: dict, classroom_id: int) -> None:
        """Leave or delete a classroom."""
        row = self._member_room(user, classroom_id)
        classroom_repository.remove_member(row["id"], user["id"])
        if classroom_repository.count_members(row["id"]) == 0:
            classroom_repository.delete(row["id"])

    def ranking(self, user: dict, classroom_id: int) -> RankingOut:
        """Return ranking rows for a classroom."""
        row = self._member_room(user, classroom_id)
        today = datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = (today - timedelta(days=6)).isoformat(timespec="seconds")
        rows = classroom_repository.ranking(row["id"], week_start)
        ranked = []
        for index, item in enumerate(rows):
            kind, stage = _tree(int(item["points"]), item.get("top_code"))
            ranked.append(
                RankingRow(
                    position=index + 1,
                    name=item["name"],
                    scans=int(item["scans"]),
                    points=int(item["points"]),
                    week_points=int(item["week_points"]),
                    co2_kg=round(float(item["co2_kg"]), 2),
                    is_me=int(item["user_id"]) == user["id"],
                    tree_kind=kind,
                    tree_stage=stage,
                )
            )
        return RankingOut(classroom=_present(row, user["id"], members=len(ranked)), rows=ranked)

    def _member_room(self, user: dict, classroom_id: int) -> dict:
        """Load a classroom the user belongs to."""
        row = classroom_repository.get(classroom_id)
        if row is None or not classroom_repository.is_member(classroom_id, user["id"]):
            raise HTTPException(status_code=404, detail="No perteneces a ese salón")
        return row

    def _require_account(self, user: dict) -> None:
        if is_guest(user):
            raise HTTPException(status_code=403, detail="Crea tu cuenta para crear o unirte a un salón")


classroom_service = ClassroomService()
