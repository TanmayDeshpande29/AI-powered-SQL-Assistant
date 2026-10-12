"""SQL generation and assistance, built on LangChain chains.

Two output styles, chosen per task:
  * structured (generate / debug / optimize): the model must fill the SQLAnswer schema,
    so our code receives typed fields (sql, explanation, assumptions, tables_used) and
    can validate the SQL before anyone sees it.
  * streamed text (explain): markdown prose for a person, sent token by token.
Rule of thumb: structure what code consumes; stream what people read.

Every call goes through with_resilience(): transient errors are retried, rate limits
switch to the other model tier. Phase 2+ adds retrieved schema context to the prompts
(that is RAG), and Phase 6 turns these steps into LangGraph agents.
"""

import logging
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Literal

from langchain_core.messages import AIMessageChunk
from langchain_core.runnables import RunnableConfig

from app.core.config import ReasoningEffort, settings
from app.core.exceptions import LLMServiceError, RateLimitedError
from app.llm.client import (
    RATE_LIMIT_ERRORS,
    LLMProvider,
    ModelTier,
    other_tier,
    retry_after_seconds,
    with_resilience,
)
from app.llm.output_schemas import SQLAnswer
from app.llm.parsers import extract_sql
from app.llm.prompts import EXPLAIN_SQL, STRUCTURED_PROMPTS, PromptSpec, schema_inputs
from app.llm.usage import estimate_cost_usd, usage_from_message
from app.schemas.llm import SQLValidation, TokenUsage
from app.sql_tools.validation import validate_sql

if TYPE_CHECKING:
    from app.services.schemas import SchemaContext

logger = logging.getLogger(__name__)

StructuredTask = Literal["generate", "debug", "optimize"]


@dataclass(frozen=True)
class LLMResult:
    """Everything one LLM call produced, independent of HTTP."""

    output: str  # SQL for structured tasks, markdown for explain
    model: str  # the model that actually answered (differs from primary after a fallback)
    prompt_version: str
    reasoning_effort: str
    latency_ms: int
    fallback_used: bool
    usage: TokenUsage | None = None
    cost_usd: Decimal | None = None
    explanation: str | None = None
    assumptions: list[str] = field(default_factory=list)
    tables_used: list[str] = field(default_factory=list)
    validation: SQLValidation | None = None
    # Phase 2: the uploaded schema that grounded the answer, if any
    schema_id: uuid.UUID | None = None
    schema_tables: list[str] = field(default_factory=list)
    schema_truncated: bool = False


def _schema_fields(context: "SchemaContext | None") -> dict[str, Any]:
    if context is None:
        return {}
    return {
        "schema_id": context.schema_id,
        "schema_tables": context.tables,
        "schema_truncated": context.truncated,
    }


def _run_config(spec: PromptSpec, effort: str, metadata: dict[str, Any] | None) -> RunnableConfig:
    """How this run is named and labelled in LangSmith traces (no effect when tracing is off)."""
    return {
        "run_name": spec.name,
        "tags": [spec.id, f"effort:{effort}"],
        "metadata": {"prompt": spec.id, "reasoning_effort": effort, **(metadata or {})},
    }


def _effort(spec: PromptSpec, requested: ReasoningEffort | None) -> ReasoningEffort:
    """The request's choice, else the prompt's own default, else the global default."""
    return requested or spec.default_reasoning_effort or settings.llm_reasoning_effort


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def _clean(items: list[str]) -> list[str]:
    return [item.strip() for item in items if item and item.strip()]


async def run_structured(
    provider: LLMProvider,
    task: StructuredTask,
    inputs: dict[str, str],
    *,
    dialect: str,
    reasoning_effort: ReasoningEffort | None = None,
    metadata: dict[str, Any] | None = None,
    schema_context: "SchemaContext | None" = None,
) -> LLMResult:
    spec = STRUCTURED_PROMPTS[task]
    effort = _effort(spec, reasoning_effort)
    inputs = {**inputs, **schema_inputs(schema_context.text if schema_context else None)}

    def structured(tier: ModelTier):
        # include_raw=True returns {"raw": AIMessage, "parsed": SQLAnswer | None,
        # "parsing_error": ...}: we need the raw message for token usage and model name.
        return provider.chat_model(tier, effort).with_structured_output(
            SQLAnswer,
            method=settings.llm_structured_output_method,
            strict=True,  # constrained decoding with json_schema; ignored otherwise
            include_raw=True,
        )

    chain = spec.template | with_resilience(structured("primary"), fallback=structured("fast"))
    started = time.perf_counter()
    try:
        result = await chain.ainvoke(inputs, config=_run_config(spec, effort, metadata))
    except RATE_LIMIT_ERRORS as exc:  # both tiers rate-limited
        raise RateLimitedError(retry_after_seconds(exc)) from exc
    except Exception as exc:
        logger.exception("LLM call failed (%s)", spec.id)
        raise LLMServiceError() from exc
    latency_ms = _elapsed_ms(started)

    answer: SQLAnswer | None = result["parsed"]
    raw = result["raw"]
    if answer is None:
        logger.warning("Unparseable structured output (%s): %s", spec.id, result["parsing_error"])
        raise LLMServiceError("The model's answer did not match the expected format. Please retry.")
    sql = extract_sql(answer.sql)  # defensive: strip markdown fences if the model added any
    if not sql:
        raise LLMServiceError("The language model returned an empty query.")

    primary = provider.model_name("primary")
    model = raw.response_metadata.get("model_name") or primary
    usage = usage_from_message(raw)
    return LLMResult(
        output=sql,
        model=model,
        prompt_version=spec.id,
        reasoning_effort=effort,
        latency_ms=latency_ms,
        fallback_used=model != primary,
        usage=usage,
        cost_usd=estimate_cost_usd(model, usage),
        explanation=answer.explanation.strip() or None,
        assumptions=_clean(answer.assumptions),
        tables_used=_clean(answer.tables_used),
        # With a schema we also check every table/column the SQL uses against it.
        validation=validate_sql(sql, dialect, schema_context.catalog if schema_context else None),
        **_schema_fields(schema_context),
    )


async def generate_sql(
    provider: LLMProvider,
    *,
    question: str,
    dialect: str,
    reasoning_effort: ReasoningEffort | None = None,
    metadata: dict[str, Any] | None = None,
    schema_context: "SchemaContext | None" = None,
) -> LLMResult:
    return await run_structured(
        provider,
        "generate",
        {"question": question, "dialect": dialect},
        dialect=dialect,
        reasoning_effort=reasoning_effort,
        metadata=metadata,
        schema_context=schema_context,
    )


async def stream_explanation(
    provider: LLMProvider,
    *,
    sql: str,
    dialect: str,
    reasoning_effort: ReasoningEffort | None = None,
    metadata: dict[str, Any] | None = None,
    schema_context: "SchemaContext | None" = None,
) -> AsyncIterator[str | LLMResult]:
    """Yield the explanation text piece by piece, then one final LLMResult."""
    spec = EXPLAIN_SQL
    effort = _effort(spec, reasoning_effort)
    tier: ModelTier = "fast"  # explaining is easy: the small model is faster and cheaper
    chain = spec.template | with_resilience(
        provider.chat_model(tier, effort),
        fallback=provider.chat_model(other_tier(tier), effort),
    )

    started = time.perf_counter()
    final: AIMessageChunk | None = None
    parts: list[str] = []
    try:
        async for chunk in chain.astream(
            {
                "sql": sql,
                "dialect": dialect,
                **schema_inputs(schema_context.text if schema_context else None, prose=True),
            },
            config=_run_config(spec, effort, metadata),
        ):
            # Adding chunks merges them: text concatenates, and the token usage that
            # arrives on the last chunk ends up on `final`.
            final = chunk if final is None else final + chunk
            text = chunk.content if isinstance(chunk.content, str) else ""
            if text:  # reasoning chunks have no visible text
                parts.append(text)
                yield text
    except RATE_LIMIT_ERRORS as exc:
        raise RateLimitedError(retry_after_seconds(exc)) from exc
    except Exception as exc:
        logger.exception("LLM stream failed (%s)", spec.id)
        raise LLMServiceError() from exc

    output = "".join(parts).strip()
    if not output:
        raise LLMServiceError("The language model returned an empty response.")
    expected = provider.model_name(tier)
    model = (final.response_metadata.get("model_name") if final else None) or expected
    usage = usage_from_message(final)
    yield LLMResult(
        output=output,
        model=model,
        prompt_version=spec.id,
        reasoning_effort=effort,
        latency_ms=_elapsed_ms(started),
        fallback_used=model != expected,
        usage=usage,
        cost_usd=estimate_cost_usd(model, usage),
        **_schema_fields(schema_context),
    )


async def explain_sql(provider: LLMProvider, **kwargs: Any) -> LLMResult:
    """Non-streaming explain: run the stream and keep only the final result."""
    result: LLMResult | None = None
    async for item in stream_explanation(provider, **kwargs):
        if isinstance(item, LLMResult):
            result = item
    if result is None:  # unreachable: the stream always ends with a result or raises
        raise LLMServiceError()
    return result


async def assist_sql(
    provider: LLMProvider,
    *,
    mode: Literal["debug", "explain", "optimize"],
    sql: str,
    dialect: str,
    reasoning_effort: ReasoningEffort | None = None,
    metadata: dict[str, Any] | None = None,
    schema_context: "SchemaContext | None" = None,
) -> LLMResult:
    if mode == "explain":
        return await explain_sql(
            provider,
            sql=sql,
            dialect=dialect,
            reasoning_effort=reasoning_effort,
            metadata=metadata,
            schema_context=schema_context,
        )
    return await run_structured(
        provider,
        mode,
        {"sql": sql, "dialect": dialect},
        dialect=dialect,
        reasoning_effort=reasoning_effort,
        metadata=metadata,
        schema_context=schema_context,
    )
