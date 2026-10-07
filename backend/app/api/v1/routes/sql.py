from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession, PrimaryLLM
from app.schemas.sql import AssistSQLRequest, GenerateSQLRequest, LLMResponse
from app.services import history as history_service
from app.services import sql as sql_service

router = APIRouter(prefix="/sql", tags=["sql"])


@router.post("/generate", response_model=LLMResponse)
async def generate(data: GenerateSQLRequest, user: CurrentUser, db: DbSession, llm: PrimaryLLM):
    result = await sql_service.generate_sql(llm, question=data.question, dialect=data.dialect)
    return await _respond(
        db, user.id, "generate", data.dialect, data.question, result, data.save_history
    )


@router.post("/assist", response_model=LLMResponse)
async def assist(data: AssistSQLRequest, user: CurrentUser, db: DbSession, llm: PrimaryLLM):
    result = await sql_service.assist_sql(llm, mode=data.mode, sql=data.sql, dialect=data.dialect)
    return await _respond(db, user.id, data.mode, data.dialect, data.sql, result, data.save_history)


async def _respond(db, user_id, tool, dialect, input_text, result, save) -> LLMResponse:
    # History is written server-side in the same request, so it can no longer be
    # silently lost by a second frontend call failing.
    entry = None
    if save:
        entry = await history_service.record(
            db,
            user_id=user_id,
            tool=tool,
            dialect=dialect,
            input_text=input_text,
            output_text=result.output,
            model=result.model,
            latency_ms=result.latency_ms,
        )
    return LLMResponse(
        output=result.output,
        model=result.model,
        latency_ms=result.latency_ms,
        history_id=entry.id if entry else None,
    )
