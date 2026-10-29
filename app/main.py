import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.env_load import load_env
from app.services.photo_service import photo_service
from app.services.vision_ai import status as gemini_status
from app.views import auth_view, classroom_view, impact_view, material_view, scan_view

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
app.include_router(classroom_view.router, prefix="/api")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    import traceback
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"detail": f"Error del servidor: {str(exc)}"},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
        },
    )


@app.get("/api/health")
def health() -> dict:
    gemini = gemini_status()
    db_ok = False
    db_type = "none"
    try:
        from app.database import get_conn
        c = get_conn()
        c.execute("SELECT 1")
        db_type = "postgres" if c.postgres else "sqlite"
        db_ok = True
        c.close()
    except Exception:
        db_ok = database_ready
    return {
        "status": "ok",
        "service": "ecoscan",
        "gemini": gemini["enabled"],
        "database": db_ok,
        "database_type": db_type,
        "vision": gemini,
    }
