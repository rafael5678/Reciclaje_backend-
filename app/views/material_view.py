from fastapi import APIRouter

from app.models.schemas import MaterialOut
from app.repositories.material_repository import MaterialRepository

router = APIRouter(tags=["materiales"])
material_repository = MaterialRepository()


@router.get("/materials", response_model=list[MaterialOut])
def list_materials() -> list[dict]:
    return material_repository.list_all()


@router.get("/materials/{code}", response_model=MaterialOut)
def get_material(code: str) -> dict:
    from fastapi import HTTPException

    material = material_repository.get(code)
    if material is None:
        raise HTTPException(status_code=404, detail="Material no encontrado")
    return material
