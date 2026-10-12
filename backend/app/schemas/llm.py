"""API-facing shapes for LLM call metadata (shared by responses and history)."""

from pydantic import BaseModel


class TokenUsage(BaseModel):
    input_tokens: int
    output_tokens: int  # includes reasoning tokens: providers bill them as output
    reasoning_tokens: int = 0  # the model's hidden "thinking" (gpt-oss), part of output
    cached_input_tokens: int = 0  # prompt prefix served from the provider's cache (cheaper)
    total_tokens: int


class SQLValidation(BaseModel):
    valid: bool  # syntax: does it parse for the dialect?
    dialect: str | None  # sqlglot dialect used, e.g. "postgres"; None = generic SQL
    statement_types: list[str] = []  # e.g. ["SELECT"], ["SELECT", "CREATE"]
    errors: list[str] = []
    # Phase 2: checked against the user's uploaded schema (only when one was used)
    schema_checked: bool = False
    schema_issues: list[str] = []  # e.g. "Unknown column: o.amount"
