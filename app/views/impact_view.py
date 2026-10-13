from fastapi import APIRouter

from app.models.schemas import ImpactOut
from app.services.impact_service import impact_service
from app.views.deps import CurrentUser

router = APIRouter(tags=["impacto"])


@router.get("/impact", response_model=ImpactOut)
def impact(user: dict = CurrentUser) -> ImpactOut:
    return impact_service.for_user(user["id"])
