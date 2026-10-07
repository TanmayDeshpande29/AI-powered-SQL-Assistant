import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
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
    model: Mapped[str] = mapped_column(String(100))
    latency_ms: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="queries")
