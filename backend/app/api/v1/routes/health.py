from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.deps import DbSession

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
async def liveness():
    """Process is up. Container orchestrators restart the app if this fails."""
    return {"status": "ok"}


@router.get("/ready")
async def readiness(db: DbSession):
    """Dependencies reachable. Load balancers stop routing traffic here if this fails."""
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse(status_code=503, content={"status": "unavailable", "database": "down"})
    return {"status": "ok", "database": "up"}
