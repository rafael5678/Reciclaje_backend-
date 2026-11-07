"""Sorting-lab route."""
from fastapi import APIRouter

from app.models.schemas import LabThrowIn, LabThrowOut
from app.services.lab_service import lab_service
from app.views.deps import CurrentUser

router = APIRouter(tags=["lab"])


@router.post("/lab/throw", response_model=LabThrowOut)
def throw_piece(body: LabThrowIn, user: dict = CurrentUser) -> LabThrowOut:
    return lab_service.throw(user["id"], body.piece_id, body.bin_id)
