from fastapi import APIRouter

from app.queue import ping as redis_ping
from app.database import engine

router = APIRouter(tags=["health"])


@router.get("/api/health")
def health():
    db_ok = True
    try:
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
    except Exception:
        db_ok = False

    return {
        "status": "ok" if db_ok else "degraded",
        "postgres": db_ok,
        "redis": redis_ping(),
    }
