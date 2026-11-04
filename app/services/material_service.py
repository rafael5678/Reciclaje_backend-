from fastapi import HTTPException

from app.repositories.material_repository import MaterialRepository


class MaterialService:
    def __init__(self) -> None:
        self._repository = MaterialRepository()

    def list_all(self) -> list[dict]:
        return self._repository.list_all()

    def get(self, code: str) -> dict | None:
        return self._repository.get(code)

    def require(self, code: str) -> dict:
        material = self.get(code)
        if material is None:
            raise HTTPException(status_code=404, detail="Material no encontrado")
        return material


material_service = MaterialService()
