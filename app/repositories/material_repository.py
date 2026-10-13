from app.models.catalog import BY_CODE, MATERIALS


class MaterialRepository:
    def list_all(self) -> list[dict]:
        return MATERIALS

    def get(self, code: str) -> dict | None:
        return BY_CODE.get(code.upper())
