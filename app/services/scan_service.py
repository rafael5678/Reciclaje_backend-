"""Create and list scans, with an optional JPEG."""
from datetime import datetime
from io import BytesIO

from fastapi import HTTPException
from PIL import Image

from app.models.schemas import ScanOut
from app.repositories.material_repository import MaterialRepository
from app.repositories.scan_repository import ScanRepository
from app.services.scan_presenter import present_scan
from app.services.score import award_points

material_repository = MaterialRepository()
scan_repository = ScanRepository()


class ScanService:
    def list_for(self, user_id: int) -> list[ScanOut]:
        return [present_scan(row) for row in scan_repository.list_by_user(user_id)]

    def create(
        self,
        user_id: int,
        material_code: str,
        object_name: str,
        confidence: float,
        separated_well: bool,
        photo: bytes | None = None,
    ) -> ScanOut:
        """Insert a new row and return it."""
        material = material_repository.get(material_code)
        if material is None:
            raise HTTPException(status_code=400, detail="Ese material no está en la guía")
        created_at = datetime.now().astimezone().isoformat(timespec="seconds")
        points, _why = award_points(material["code"], confidence, separated_well)
        row = scan_repository.insert(
            user_id=user_id,
            material_code=material["code"],
            object_name=object_name.strip(),
            confidence=confidence,
            separated_well=separated_well,
            points=points,
            weight_kg=material["weight_kg"],
            co2_kg=material["co2_kg"] if separated_well else 0,
            created_at=created_at,
            photo=_jpeg(photo) if photo else None,
        )
        return present_scan(row)

    def photo_for(self, user_id: int, scan_id: int) -> bytes | None:
        """Return the JPEG bytes for a scan the user owns."""
        return scan_repository.photo_for(user_id, scan_id)


def _jpeg(raw: bytes) -> bytes | None:
    try:
        image = Image.open(BytesIO(raw))
        image = image.convert("RGB")
        image.thumbnail((720, 720))
        out = BytesIO()
        image.save(out, format="JPEG", quality=82)
        return out.getvalue()
    except Exception:
        return None


scan_service = ScanService()
