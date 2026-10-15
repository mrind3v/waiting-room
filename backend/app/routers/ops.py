from functools import lru_cache
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db

router = APIRouter()


@lru_cache
def _alembic_head() -> str:
    cfg = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    cfg.set_main_option("script_location", str(Path(__file__).resolve().parents[2] / "alembic"))
    return ScriptDirectory.from_config(cfg).get_current_head()


@router.get("/")
def root():
    s = get_settings()
    return {"service": s.app_name, "version": s.git_sha, "docs": "/docs"}


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/ready")
def ready(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        current = db.execute(text("SELECT version_num FROM alembic_version")).scalar()
        if current != _alembic_head():
            return JSONResponse(
                {"status": "not-ready", "detail": f"schema at {current}, expected head"},
                status_code=503,
            )
    except Exception as exc:  # noqa: BLE001 - any failure means "not ready"
        return JSONResponse({"status": "not-ready", "detail": type(exc).__name__}, status_code=503)
    return {"status": "ready"}


@router.get("/api/config")
def config():
    s = get_settings()
    return {"clinic_tz": s.clinic_tz, "version": s.git_sha}
