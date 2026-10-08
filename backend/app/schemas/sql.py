import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.config import ReasoningEffort
from app.schemas.llm import SQLValidation, TokenUsage

AssistMode = Literal["debug", "explain", "optimize"]
Tool = Literal["generate", "debug", "explain", "optimize"]

MAX_INPUT_CHARS = 20_000  # protects the LLM context window and our token budget


class _LLMRequest(BaseModel):
    dialect: str = Field(default="PostgreSQL", max_length=40)
    save_history: bool = True
    # How long the model "thinks" before answering: low = fastest/cheapest,
    # high = most careful. None = the server default (LLM_REASONING_EFFORT).
    reasoning_effort: ReasoningEffort | None = None


class GenerateSQLRequest(_LLMRequest):
    question: str = Field(min_length=3, max_length=MAX_INPUT_CHARS)


class AssistSQLRequest(_LLMRequest):
    mode: AssistMode
    sql: str = Field(min_length=1, max_length=MAX_INPUT_CHARS)


class ExplainSQLRequest(_LLMRequest):
    sql: str = Field(min_length=1, max_length=MAX_INPUT_CHARS)


class LLMResponse(BaseModel):
    output: str  # SQL (generate/debug/optimize) or markdown (explain)
    explanation: str | None = None
    assumptions: list[str] = []
    tables_used: list[str] = []
    validation: SQLValidation | None = None  # None for explain (no SQL produced)
    model: str
    prompt_version: str
    reasoning_effort: str
    latency_ms: int
    usage: TokenUsage | None = None
    cost_usd: float | None = None  # list-price estimate in USD
    fallback_used: bool = False
    history_id: uuid.UUID | None = None


class QueryHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tool: Tool
    dialect: str
    input_text: str
    output_text: str
    model: str
    latency_ms: int
    created_at: datetime
    prompt_version: str | None = None
    reasoning_effort: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    reasoning_tokens: int | None = None
    cost_usd: float | None = None
    details: dict[str, Any] | None = None


class QueryHistoryPage(BaseModel):
    items: list[QueryHistoryRead]
    total: int
    limit: int
    offset: int
