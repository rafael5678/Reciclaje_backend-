from datetime import datetime

from fastapi import HTTPException

from app.models.schemas import ScanOut
from app.repositories.material_repository import MaterialRepository
from app.repositories.scan_repository import ScanRepository

material_repository = MaterialRepository()
scan_repository = ScanRepository()
POINTS_PER_SCAN = 10


def present_scan(row: dict) -> ScanOut:
    material = material_repository.get(row["material_code"])
    if material is None:
        raise HTTPException(status_code=500, detail="Material desconocido en el historial")
    return ScanOut(
        id=row["id"],
        material_code=material["code"],
        material_name=material["name"],
        full_name=material["full_name"],
        category=material["category"],
        object_name=row["object_name"],
        confidence=float(row["confidence"]),
        container=material["container"],
        container_detail=material["container_detail"],
        tone=material["tone"],
        steps=material["steps"],
        primary_action=material["primary_action"],
        points=int(row["points"]),
        weight_kg=float(row["weight_kg"]),
        co2_kg=float(row["co2_kg"]),
        created_at=row["created_at"],
        separated_well=bool(row["separated_well"]),
        accent=material["accent"],
        warning=material["warning"],
        recyclable=material["recyclable"],
    )


class ScanService:
    def list_for(self, user_id: int) -> list[ScanOut]:
        return [present_scan(row) for row in scan_repository.list_by_user(user_id)]

    def create(self, user_id: int, material_code: str, object_name: str, confidence: float, separated_well: bool) -> ScanOut:
        material = material_repository.get(material_code)
        if material is None:
            raise HTTPException(status_code=400, detail="Ese material no está en la guía")
        created_at = datetime.now().astimezone().isoformat(timespec="seconds")
        row = scan_repository.insert(
            user_id=user_id,
            material_code=material["code"],
            object_name=object_name.strip(),
            confidence=confidence,
            separated_well=separated_well,
            points=POINTS_PER_SCAN,
            weight_kg=material["weight_kg"],
            co2_kg=material["co2_kg"] if separated_well else 0,
            created_at=created_at,
        )
        return present_scan(row)


scan_service = ScanService()
