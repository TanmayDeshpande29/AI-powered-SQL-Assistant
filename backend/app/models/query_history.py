import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKeyMixin, utcnow

if TYPE_CHECKING:
    from app.models.user import User


class QueryHistory(UUIDPrimaryKeyMixin, Base):
    """One row per AI request (generate / debug / explain / optimize)."""

    __tablename__ = "query_history"
    # Composite index: the history page always asks "this user's rows, newest first".
    __table_args__ = (Index("ix_query_history_user_id_created_at", "user_id", "created_at"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    tool: Mapped[str] = mapped_column(String(32))
    dialect: Mapped[str] = mapped_column(String(40))
    input_text: Mapped[str] = mapped_column(Text)
    output_text: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(String(100))  # the model that actually answered
    latency_ms: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )

    # --- Phase 1: LLM observability (nullable: rows from Phase 0 don't have them) ---
    prompt_version: Mapped[str | None] = mapped_column(String(64))  # e.g. "generate_sql@v2"
    reasoning_effort: Mapped[str | None] = mapped_column(String(10))
    input_tokens: Mapped[int | None]
    output_tokens: Mapped[int | None]  # includes reasoning tokens
    reasoning_tokens: Mapped[int | None]
    # Numeric, not Float: exact decimal arithmetic for money (12 digits, 8 after the point).
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    # Structured extras: explanation, assumptions, tables_used, validation, fallback_used.
    # JSONB on PostgreSQL (binary, indexable, queryable); plain JSON elsewhere (tests).
    details: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql")
    )

    user: Mapped["User"] = relationship(back_populates="queries")
