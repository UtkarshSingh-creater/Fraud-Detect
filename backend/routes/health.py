from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text
import time

from database import AsyncSessionLocal
from core.connection_manager import manager
from routes.sessions import sessions

router = APIRouter(tags=["Health"])   # ← NO prefix here

_start_time = time.time()


@router.get("/health")               # ← full path here instead
async def health_check():
    db_status = "ok"
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"error: {e}"

    return JSONResponse(
        status_code=200 if db_status == "ok" else 503,
        content={
            "status":          "healthy" if db_status == "ok" else "degraded",
            "version":         "1.0.0",
            "uptime_seconds":  round(time.time() - _start_time, 1),
            "checks": {
                "database":            db_status,
                "active_sessions":     len(sessions),
                "connected_agents":    len(manager.agent_connections),
                "connected_dashboards": len(manager.dashboard_connections),
            },
        }
    )


@router.get("/health/live")
def liveness():
    return {"alive": True}


@router.get("/health/ready")
async def readiness():
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
        return {"ready": True}
    except Exception as e:
        return JSONResponse(status_code=503, content={"ready": False, "reason": str(e)})