from io import BytesIO

from fastapi import APIRouter, File, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError

from app.models.schemas import AnalyzeOut, ScanIn, ScanOut
from app.services.photo_service import photo_service
from app.services.scan_service import scan_service
from app.views.deps import CurrentUser

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
def create_scan(body: ScanIn, user: dict = CurrentUser) -> ScanOut:
    return scan_service.create(
        user_id=user["id"],
        material_code=body.material_code,
        object_name=body.object_name,
        confidence=body.confidence,
        separated_well=body.separated_well,
    )
