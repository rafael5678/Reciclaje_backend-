from fastapi import APIRouter, Response

from app.models.schemas import ClassroomIn, ClassroomOut, JoinIn, RankingOut
from app.services.classroom_service import classroom_service
from app.views.deps import CurrentUser

router = APIRouter(tags=["salones"])


@router.get("/classrooms", response_model=list[ClassroomOut])
def list_classrooms(user: dict = CurrentUser) -> list[ClassroomOut]:
    return classroom_service.list_for(user)


@router.post("/classrooms", response_model=ClassroomOut)
def create_classroom(body: ClassroomIn, user: dict = CurrentUser) -> ClassroomOut:
    return classroom_service.create(user, body.name)


@router.post("/classrooms/join", response_model=ClassroomOut)
def join_classroom(body: JoinIn, user: dict = CurrentUser) -> ClassroomOut:
    return classroom_service.join(user, body.code)


@router.get("/classrooms/{classroom_id}/ranking", response_model=RankingOut)
def classroom_ranking(classroom_id: int, user: dict = CurrentUser) -> RankingOut:
    return classroom_service.ranking(user, classroom_id)


@router.delete("/classrooms/{classroom_id}/membership", status_code=204)
def leave_classroom(classroom_id: int, user: dict = CurrentUser) -> Response:
    classroom_service.leave(user, classroom_id)
    return Response(status_code=204)
