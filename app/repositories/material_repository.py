"""In-memory material catalog reads."""
from app.models.catalog import BY_CODE, MATERIALS


class MaterialRepository:
    def list_all(self) -> list[dict]:
        """Return the full catalog."""
        return MATERIALS

    def get(self, code: str) -> dict | None:
        return BY_CODE.get(code.upper())
