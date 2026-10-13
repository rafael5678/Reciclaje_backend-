import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.env_load import load_env
from app.services.photo_service import photo_service
from app.services.vision_ai import has_gemini
from app.views import auth_view, impact_view, material_view, scan_view

load_env()


database_ready = False


@asynccontextmanager
async def lifespan(_: FastAPI):
    global database_ready
    database_ready = init_db()
    try:
        photo_service.warmup()
    except Exception:
        pass
    yield


app = FastAPI(title="EcoScan API", version="1.0.0", lifespan=lifespan)
_origins = [item.strip() for item in os.environ.get("FRONTEND_URL", "*").split(",") if item.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins or ["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_view.router, prefix="/api")
app.include_router(material_view.router, prefix="/api")
app.include_router(scan_view.router, prefix="/api")
app.include_router(impact_view.router, prefix="/api")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "service": "ecoscan", "gemini": has_gemini(), "database": database_ready}
