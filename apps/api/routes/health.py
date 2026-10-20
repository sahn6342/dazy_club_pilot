import logging
import os
from functools import lru_cache

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from brand import BRAND_NAME
from db import _BASE_DIR, _session
from observability import sweep_status
from services.notification_service import delivery_status

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health")
def health():
    """Liveness: is the process up? Deliberately does not touch the database (Render calls it
    often and must not wake a suspended Neon compute)."""
    return {"status": "ok", "app": f"{BRAND_NAME} API"}


@lru_cache(maxsize=1)
def _migration_head() -> str | None:
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    cfg = Config(os.path.join(_BASE_DIR, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(_BASE_DIR, "alembic"))
    return ScriptDirectory.from_config(cfg).get_current_head()


def _delivery() -> dict:
    try:
        return delivery_status()
    except Exception:  # informational only: never let it turn a healthy DB into a 503
        logger.exception("delivery_status failed")
        return {"providers": {}, "warnings": ["delivery status unavailable"], "queue": {}}


@router.get("/health/ready")
def ready():
    """Readiness, for the uptime monitor: the database answers AND the schema is at the migration
    head this code expects. 503 otherwise. Public but reveals nothing sensitive; it also shows when
    the scheduler last ran. Point an external monitor here (every ~5 minutes; that keeps Neon awake)."""
    try:
        with _session() as s:
            s.execute(text("SELECT 1"))
            revision = s.execute(text("SELECT version_num FROM alembic_version")).scalar()
    except Exception:
        logger.exception("Readiness check: database unavailable")
        return JSONResponse(status_code=503, content={"status": "degraded", "db": "error"})
    head = _migration_head()
    migrated = revision == head
    if not migrated:
        logger.error("Readiness check: schema at %s but code expects %s", revision, head)
    return JSONResponse(
        status_code=200 if migrated else 503,
        content={"status": "ok" if migrated else "degraded", "db": "ok", "migrated": migrated,
                 "revision": revision, "head": head, "sweep": sweep_status(), "notifications": _delivery()},
    )
