import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AssistMode = Literal["debug", "explain", "optimize"]
Tool = Literal["generate", "debug", "explain", "optimize"]

MAX_INPUT_CHARS = 20_000  # protects the LLM context window and our token budget


class GenerateSQLRequest(BaseModel):
    question: str = Field(min_length=3, max_length=MAX_INPUT_CHARS)
    dialect: str = Field(default="PostgreSQL", max_length=40)
    save_history: bool = True


class AssistSQLRequest(BaseModel):
    mode: AssistMode
    sql: str = Field(min_length=1, max_length=MAX_INPUT_CHARS)
    dialect: str = Field(default="PostgreSQL", max_length=40)
    save_history: bool = True


class LLMResponse(BaseModel):
    output: str
    model: str
    latency_ms: int
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


class QueryHistoryPage(BaseModel):
    items: list[QueryHistoryRead]
    total: int
    limit: int
    offset: int
