"""Factory for LangChain chat models backed by Groq.

Two tiers keep cost/latency in check as the agent graph grows:
  primary -> large model for SQL generation and reasoning
  fast    -> small model for cheap steps (routing, query rewriting, judging)

Routes receive the model through FastAPI dependencies (get_primary_llm), so tests
can swap in a fake model without touching the network.
"""

from functools import lru_cache
from typing import Literal

from langchain_core.language_models import BaseChatModel
from langchain_groq import ChatGroq

from app.core.config import settings

ModelTier = Literal["primary", "fast"]


@lru_cache
def get_chat_model(tier: ModelTier = "primary") -> BaseChatModel:
    model = settings.llm_model_primary if tier == "primary" else settings.llm_model_fast
    return ChatGroq(
        model=model,
        api_key=settings.groq_api_key,
        temperature=settings.llm_temperature,
        timeout=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,  # retries 429/5xx with exponential backoff
    )


def get_primary_llm() -> BaseChatModel:
    """FastAPI dependency."""
    return get_chat_model("primary")


def model_name(llm: BaseChatModel) -> str:
    return getattr(llm, "model_name", None) or getattr(llm, "model", None) or type(llm).__name__
