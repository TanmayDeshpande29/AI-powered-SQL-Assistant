import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models import QueryHistory
from app.services.sql import LLMResult


async def record(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    tool: str,
    dialect: str,
    input_text: str,
    result: LLMResult,
) -> QueryHistory:
    usage = result.usage
    details = {
        "explanation": result.explanation,
        "assumptions": result.assumptions,
        "tables_used": result.tables_used,
        "validation": result.validation.model_dump() if result.validation else None,
        "fallback_used": result.fallback_used,
        "schema_tables": result.schema_tables,
        "schema_truncated": result.schema_truncated,
    }
    entry = QueryHistory(
        user_id=user_id,
        tool=tool,
        dialect=dialect,
        input_text=input_text,
        output_text=result.output,
        model=result.model,
        latency_ms=result.latency_ms,
        prompt_version=result.prompt_version,
        reasoning_effort=result.reasoning_effort,
        input_tokens=usage.input_tokens if usage else None,
        output_tokens=usage.output_tokens if usage else None,
        reasoning_tokens=usage.reasoning_tokens if usage else None,
        cost_usd=result.cost_usd,
        details=details,
        schema_id=result.schema_id,
    )
    db.add(entry)
    await db.commit()
    return entry


async def list_for_user(
    db: AsyncSession, user_id: uuid.UUID, *, limit: int, offset: int
) -> tuple[list[QueryHistory], int]:
    owned = QueryHistory.user_id == user_id  # every query is scoped to the caller
    total = await db.scalar(select(func.count()).select_from(QueryHistory).where(owned))
    rows = await db.scalars(
        select(QueryHistory)
        .where(owned)
        .order_by(QueryHistory.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(rows), total or 0


async def delete_for_user(db: AsyncSession, user_id: uuid.UUID, entry_id: uuid.UUID) -> None:
    result = await db.execute(
        delete(QueryHistory).where(QueryHistory.id == entry_id, QueryHistory.user_id == user_id)
    )
    if result.rowcount == 0:
        # Same answer for "doesn't exist" and "belongs to someone else":
        # never confirm that another user's id exists.
        raise NotFoundError("History entry not found.")
    await db.commit()
