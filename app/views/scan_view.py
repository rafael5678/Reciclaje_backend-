from io import BytesIO

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import Response
from PIL import Image, UnidentifiedImageError

from app.models.schemas import AnalyzeOut, ScanIn, ScanOut
from app.repositories.scan_repository import ScanRepository
from app.services.photo_service import photo_service
from app.services.scan_service import scan_service
from app.views.deps import CurrentUser

scan_repository = ScanRepository()

router = APIRouter(tags=["escaneos"])


@router.get("/scans", response_model=list[ScanOut])
def list_scans(user: dict = CurrentUser) -> list[ScanOut]:
    return scan_service.list_for(user["id"])


@router.post("/analyze", response_model=AnalyzeOut)
async def analyze_photo(file: UploadFile = File(...), user: dict = CurrentUser) -> AnalyzeOut:
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="La foto llegó vacía")
    if len(raw) > 12 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="La foto pesa demasiado. Usa una de menos de 12 MB")
    try:
        image = Image.open(BytesIO(raw))
        image.load()
    except (UnidentifiedImageError, OSError):
        raise HTTPException(status_code=400, detail="Ese archivo no es una imagen. Prueba con JPG o PNG")
    photo_service.save_upload(raw, file.filename or "foto.jpg", str(user["id"]))
    return photo_service.analyze(image)


@router.post("/scans", response_model=ScanOut)
async def create_scan(request: Request, user: dict = CurrentUser) -> ScanOut:
    photo: bytes | None = None
    if "multipart/form-data" in request.headers.get("content-type", ""):
        form = await request.form()
        body = ScanIn(
            material_code=str(form.get("material_code") or ""),
            object_name=str(form.get("object_name") or ""),
            confidence=float(str(form.get("confidence") or 0)),
            separated_well=str(form.get("separated_well") or "true").lower() not in {"false", "0", ""},
        )
        upload = form.get("file")
        if upload is not None and hasattr(upload, "read"):
            photo = await upload.read()
    else:
        body = ScanIn.model_validate(await request.json())
    return scan_service.create(
        user_id=user["id"],
        material_code=body.material_code,
        object_name=body.object_name,
        confidence=body.confidence,
        separated_well=body.separated_well,
        photo=photo,
    )


@router.get("/scans/{scan_id}/photo")
def scan_photo(scan_id: int, user: dict = CurrentUser) -> Response:
    raw = scan_repository.photo_for(user["id"], scan_id)
    if not raw:
        raise HTTPException(status_code=404, detail="Esta foto ya no está guardada")
    return Response(content=raw, media_type="image/jpeg")
