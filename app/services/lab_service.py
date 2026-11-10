"""Grade a lab throw without changing scan history."""
from datetime import datetime

from fastapi import HTTPException

from app.models.lab_catalog import lab_catalog
from app.models.schemas import LabThrowOut
from app.repositories.lab_repository import lab_repository
from app.repositories.scan_repository import ScanRepository

scan_repository = ScanRepository()


class LabService:
    def throw(self, user_id: int, piece_id: str, bin_id: str) -> LabThrowOut:
        piece = lab_catalog.piece(piece_id)
        chosen = lab_catalog.bin(bin_id)
        if piece is None or chosen is None:
            raise HTTPException(status_code=400, detail="Esa pieza o caneca no está en el laboratorio")
        expected = lab_catalog.bin(piece["bin_id"])
        if expected is None:
            raise HTTPException(status_code=400, detail="Esa pieza o caneca no está en el laboratorio")
        correct = piece["bin_id"] == bin_id
        delta = 0 if correct else -lab_catalog.mistake_cost
        lab_repository.insert(
            user_id=user_id,
            piece_id=piece_id,
            bin_id=bin_id,
            correct=correct,
            delta=delta,
            created_at=datetime.now().astimezone().isoformat(timespec="seconds"),
        )
        lab_penalty = lab_repository.delta_for(user_id)
        points = max(0, scan_repository.points_for(user_id) + lab_penalty)
        hint = piece["hint"] if correct else f"No va al {chosen['title']}. {piece['hint']}"
        return LabThrowOut(
            correct=correct,
            delta=delta,
            points=points,
            lab_penalty=lab_penalty,
            hint=hint,
            piece_title=piece["title"],
            bin_title=chosen["title"],
            expected_bin=expected["title"],
        )


lab_service = LabService()
