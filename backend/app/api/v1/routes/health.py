from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.deps import DbSession, VectorIndex

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
async def liveness():
    """Process is up. Container orchestrators restart the app if this fails."""
    return {"status": "ok"}


@router.get("/ready")
async def readiness(db: DbSession, index: VectorIndex):
    """Dependencies reachable. Load balancers stop routing traffic here if this fails.

    Only the database is critical: without the vector store, search is down but the
    rest of the app (and the ingestion of uploads) still works.
    """
    vector_store = "up" if await index.ping() else "down"
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable", "database": "down", "vector_store": vector_store},
        )
    return {"status": "ok", "database": "up", "vector_store": vector_store}
