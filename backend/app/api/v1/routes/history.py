import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.sql import QueryHistoryPage
from app.services import history as history_service

router = APIRouter(prefix="/history", tags=["history"])


@router.get("", response_model=QueryHistoryPage)
async def list_history(
    user: CurrentUser,
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    items, total = await history_service.list_for_user(db, user.id, limit=limit, offset=offset)
    return QueryHistoryPage(items=items, total=total, limit=limit, offset=offset)


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_history_entry(entry_id: uuid.UUID, user: CurrentUser, db: DbSession):
    await history_service.delete_for_user(db, user.id, entry_id)
