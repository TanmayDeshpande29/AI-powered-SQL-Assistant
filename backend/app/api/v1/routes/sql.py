import logging
from collections.abc import AsyncIterable

from fastapi import APIRouter
from fastapi.sse import EventSourceResponse, ServerSentEvent
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import LLM, CurrentUser, DbSession
from app.core.exceptions import AppError
from app.db.session import release_connection
from app.models import User
from app.schemas.sql import AssistSQLRequest, ExplainSQLRequest, GenerateSQLRequest, LLMResponse
from app.services import history as history_service
from app.services import schemas as schema_service
from app.services import sql as sql_service
from app.services.schemas import SchemaContext
from app.services.sql import LLMResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sql", tags=["sql"])


def _trace_metadata(user: User) -> dict[str, str]:
    return {"user_id": str(user.id)}  # lets you filter LangSmith traces per user


async def _schema_context(db: AsyncSession, user: User, data) -> SchemaContext | None:
    """Load the selected schema (404 if it isn't the user's) while we still hold the
    DB connection, i.e. before release_connection()."""
    if data.schema_id is None:
        return None
    return await schema_service.build_context(db, user.id, data.schema_id, data.tables)


async def _respond(
    db: AsyncSession,
    user: User,
    *,
    tool: str,
    dialect: str,
    input_text: str,
    result: LLMResult,
    save: bool,
) -> LLMResponse:
    entry = None
    if save:  # history is written in the same request, so it can't be silently lost
        entry = await history_service.record(
            db, user_id=user.id, tool=tool, dialect=dialect, input_text=input_text, result=result
        )
    return LLMResponse(
        output=result.output,
        explanation=result.explanation,
        assumptions=result.assumptions,
        tables_used=result.tables_used,
        validation=result.validation,
        model=result.model,
        prompt_version=result.prompt_version,
        reasoning_effort=result.reasoning_effort,
        latency_ms=result.latency_ms,
        usage=result.usage,
        cost_usd=float(result.cost_usd) if result.cost_usd is not None else None,
        fallback_used=result.fallback_used,
        history_id=entry.id if entry else None,
        schema_id=result.schema_id,
        schema_tables=result.schema_tables,
        schema_truncated=result.schema_truncated,
    )


@router.post("/generate", response_model=LLMResponse)
async def generate(data: GenerateSQLRequest, user: CurrentUser, db: DbSession, llm: LLM):
    context = await _schema_context(db, user, data)
    await release_connection(db)  # don't hold a DB connection during the LLM call
    result = await sql_service.generate_sql(
        llm,
        question=data.question,
        dialect=data.dialect,
        reasoning_effort=data.reasoning_effort,
        metadata=_trace_metadata(user),
        schema_context=context,
    )
    return await _respond(
        db,
        user,
        tool="generate",
        dialect=data.dialect,
        input_text=data.question,
        result=result,
        save=data.save_history,
    )


@router.post("/assist", response_model=LLMResponse)
async def assist(data: AssistSQLRequest, user: CurrentUser, db: DbSession, llm: LLM):
    context = await _schema_context(db, user, data)
    await release_connection(db)
    result = await sql_service.assist_sql(
        llm,
        mode=data.mode,
        sql=data.sql,
        dialect=data.dialect,
        reasoning_effort=data.reasoning_effort,
        metadata=_trace_metadata(user),
        schema_context=context,
    )
    return await _respond(
        db,
        user,
        tool=data.mode,
        dialect=data.dialect,
        input_text=data.sql,
        result=result,
        save=data.save_history,
    )


@router.post("/explain/stream", response_class=EventSourceResponse)
async def explain_stream(
    data: ExplainSQLRequest, user: CurrentUser, db: DbSession, llm: LLM
) -> AsyncIterable[ServerSentEvent]:
    """Stream an explanation as Server-Sent Events.

    Events: `token` {"text": ...} many times, then exactly one of
            `done`  (the full LLMResponse, incl. usage and history_id) or
            `error` {"code", "message", "details"}.
    Auth and body validation run before streaming starts, so they still return normal
    401/422 JSON errors. Once the stream has begun the status code (200) is already
    sent, so later failures can only be reported as an `error` event (that includes
    an unknown schema_id, which is looked up inside the stream).
    """
    result: LLMResult | None = None
    try:
        context = await _schema_context(db, user, data)
        await release_connection(db)
        async for item in sql_service.stream_explanation(
            llm,
            sql=data.sql,
            dialect=data.dialect,
            reasoning_effort=data.reasoning_effort,
            metadata=_trace_metadata(user),
            schema_context=context,
        ):
            if isinstance(item, LLMResult):
                result = item
            else:
                yield ServerSentEvent(event="token", data={"text": item})
        if result is None:
            raise AppError()
        response = await _respond(
            db,
            user,
            tool="explain",
            dialect=data.dialect,
            input_text=data.sql,
            result=result,
            save=data.save_history,
        )
    except AppError as exc:
        error = {"code": exc.code, "message": exc.message, "details": exc.details}
        yield ServerSentEvent(event="error", data=error)
        return
    except Exception:
        logger.exception("Unexpected error while streaming an explanation")
        error = {"code": AppError.code, "message": AppError.message, "details": None}
        yield ServerSentEvent(event="error", data=error)
        return
    yield ServerSentEvent(event="done", data=response)
