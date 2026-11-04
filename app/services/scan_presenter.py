"""Map a scan row to the ScanOut DTO."""
from datetime import datetime

from fastapi import HTTPException

from app.models.schemas import ScanOut
from app.repositories.material_repository import MaterialRepository

material_repository = MaterialRepository()


class ScanPresenter:
    def present(self, row: dict) -> ScanOut:
        """Map a database scan row to ScanOut."""
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
            created_at=self.as_text(row["created_at"]),
            separated_well=bool(row["separated_well"]),
            accent=material["accent"],
            warning=material["warning"],
            recyclable=material["recyclable"],
            has_photo=bool(row.get("has_photo")),
        )

    def as_text(self, value) -> str:
        """Normalize timestamps to ISO text."""
        if isinstance(value, datetime):
            return value.isoformat()
        return str(value)


scan_presenter = ScanPresenter()


def present_scan(row: dict) -> ScanOut:
    return scan_presenter.present(row)
