"""Material catalog routes."""
from fastapi import APIRouter

from app.models.schemas import MaterialOut
from app.services.material_service import material_service

router = APIRouter(tags=["materiales"])


@router.get("/materials", response_model=list[MaterialOut])
def list_materials() -> list[dict]:
    return material_service.list_all()


@router.get("/materials/{code}", response_model=MaterialOut)
def get_material(code: str) -> dict:
    return material_service.require(code)
