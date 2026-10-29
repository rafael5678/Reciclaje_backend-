import secrets
from datetime import datetime, timedelta

from fastapi import HTTPException

from app.models.schemas import ClassroomOut, RankingOut, RankingRow
from app.repositories.classroom_repository import ClassroomRepository
from app.services.auth_service import is_guest

classroom_repository = ClassroomRepository()
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
MAX_CLASSROOMS = 10


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _present(row: dict, user_id: int, members: int | None = None) -> ClassroomOut:
    return ClassroomOut(
        id=row["id"],
        name=row["name"],
        code=row["code"],
        members=int(members if members is not None else row.get("members", 0)),
        is_owner=int(row["owner_id"]) == user_id,
    )


class ClassroomService:
    def list_for(self, user: dict) -> list[ClassroomOut]:
        return [_present(row, user["id"]) for row in classroom_repository.for_user(user["id"])]

    def create(self, user: dict, name: str) -> ClassroomOut:
        self._require_account(user)
        if len(classroom_repository.for_user(user["id"])) >= MAX_CLASSROOMS:
            raise HTTPException(status_code=400, detail=f"Puedes estar en máximo {MAX_CLASSROOMS} salones")
        for _ in range(5):
            code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(6))
            if classroom_repository.by_code(code) is None:
                row = classroom_repository.create(name, code, user["id"], _now())
                return _present(row, user["id"], members=1)
        raise HTTPException(status_code=500, detail="No pude generar un código. Intenta otra vez")

    def join(self, user: dict, code: str) -> ClassroomOut:
        self._require_account(user)
        row = classroom_repository.by_code(code.strip().upper())
        if row is None:
            raise HTTPException(status_code=404, detail="No existe un salón con ese código")
        if not classroom_repository.is_member(row["id"], user["id"]):
            if len(classroom_repository.for_user(user["id"])) >= MAX_CLASSROOMS:
                raise HTTPException(status_code=400, detail=f"Puedes estar en máximo {MAX_CLASSROOMS} salones")
            classroom_repository.add_member(row["id"], user["id"], _now())
        return _present(row, user["id"], members=classroom_repository.count_members(row["id"]))

    def leave(self, user: dict, classroom_id: int) -> None:
        row = self._member_room(user, classroom_id)
        classroom_repository.remove_member(row["id"], user["id"])
        if classroom_repository.count_members(row["id"]) == 0:
            classroom_repository.delete(row["id"])

    def ranking(self, user: dict, classroom_id: int) -> RankingOut:
        row = self._member_room(user, classroom_id)
        today = datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = (today - timedelta(days=6)).isoformat(timespec="seconds")
        rows = classroom_repository.ranking(row["id"], week_start)
        ranked = [
            RankingRow(
                position=index + 1,
                name=item["name"],
                scans=int(item["scans"]),
                points=int(item["points"]),
                week_points=int(item["week_points"]),
                co2_kg=round(float(item["co2_kg"]), 2),
                is_me=int(item["user_id"]) == user["id"],
            )
            for index, item in enumerate(rows)
        ]
        return RankingOut(classroom=_present(row, user["id"], members=len(ranked)), rows=ranked)

    def _member_room(self, user: dict, classroom_id: int) -> dict:
        row = classroom_repository.get(classroom_id)
        if row is None or not classroom_repository.is_member(classroom_id, user["id"]):
            raise HTTPException(status_code=404, detail="No perteneces a ese salón")
        return row

    def _require_account(self, user: dict) -> None:
        if is_guest(user):
            raise HTTPException(status_code=403, detail="Crea tu cuenta para crear o unirte a un salón")


classroom_service = ClassroomService()
