"""LangChain chat models backed by Groq, and the resilience policy around them.

Two tiers keep cost and latency in check:
  primary -> large model (gpt-oss-120b): SQL generation, debugging, optimizing
  fast    -> small model (gpt-oss-20b):  explanations; later routing and judging
Each tier is also the other's fallback when the provider rate-limits us.

Services ask an LLMProvider for models. It is a FastAPI dependency, so tests swap in
fakes without touching the network.
"""

from functools import lru_cache
from typing import Literal

import groq
from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import Runnable
from langchain_groq import ChatGroq

from app.core.config import ReasoningEffort, settings

ModelTier = Literal["primary", "fast"]

# Worth retrying on the same model: network trouble, timeouts, 5xx from the provider.
TRANSIENT_ERRORS: tuple[type[Exception], ...] = (groq.APIConnectionError, groq.InternalServerError)
# Waiting is pointless for this request: switch to the other model immediately.
RATE_LIMIT_ERRORS: tuple[type[Exception], ...] = (groq.RateLimitError,)


def model_for(tier: ModelTier) -> str:
    return settings.llm_model_primary if tier == "primary" else settings.llm_model_fast


def other_tier(tier: ModelTier) -> ModelTier:
    return "fast" if tier == "primary" else "primary"


@lru_cache
def get_chat_model(
    tier: ModelTier = "primary", reasoning_effort: ReasoningEffort | None = None
) -> BaseChatModel:
    """One cached client per (tier, effort): at most 6 instances, reused across requests."""
    return ChatGroq(
        model=model_for(tier),
        api_key=settings.groq_api_key,
        temperature=settings.llm_temperature,
        timeout=settings.llm_timeout_seconds,
        max_tokens=settings.llm_max_output_tokens,
        reasoning_effort=reasoning_effort or settings.llm_reasoning_effort,
        # The Groq SDK would retry rate limits by itself, sleeping for the server's
        # Retry-After (up to 60 s) on every attempt. We turn that off and decide
        # ourselves in with_resilience(): retry transient errors, fall back on 429.
        max_retries=0,
    )


@lru_cache
def get_vision_model() -> BaseChatModel:
    """The image-capable model (Phase 2: reading schema screenshots).

    Its reasoning switch is model-specific ("none" for Qwen), so it is configured
    separately from the gpt-oss tiers. Transcribing is perception, not reasoning.
    """
    extra = {}
    if settings.llm_vision_reasoning_effort:
        extra = {
            "reasoning_effort": settings.llm_vision_reasoning_effort,
            "reasoning_format": "parsed",
        }
    return ChatGroq(
        model=settings.llm_model_vision,
        api_key=settings.groq_api_key,
        temperature=0,  # transcription: we want the most likely reading, not creativity
        timeout=settings.llm_timeout_seconds,
        max_tokens=settings.llm_max_output_tokens,
        max_retries=0,
        **extra,
    )


def with_resilience(runnable: Runnable, fallback: Runnable | None = None) -> Runnable:
    """Retry transient failures with exponential backoff + jitter; on a rate limit,
    switch to `fallback` instead of waiting."""

    def with_retries(r: Runnable) -> Runnable:
        return r.with_retry(
            retry_if_exception_type=TRANSIENT_ERRORS,
            stop_after_attempt=settings.llm_max_retries + 1,
            wait_exponential_jitter=True,
            exponential_jitter_params={"initial": 0.5, "max": 4},
        )

    resilient = with_retries(runnable)
    if fallback is not None:
        resilient = resilient.with_fallbacks(
            [with_retries(fallback)], exceptions_to_handle=RATE_LIMIT_ERRORS
        )
    return resilient


def retry_after_seconds(exc: BaseException) -> int | None:
    """Seconds the provider asked us to wait (its Retry-After header), if it said."""
    response = getattr(exc, "response", None)
    value = response.headers.get("retry-after") if response is not None else None
    try:
        return max(1, round(float(value))) if value else None
    except ValueError:  # Retry-After may also be an HTTP date; treat as unknown
        return None


class LLMProvider:
    """Hands out chat models by tier and reasoning effort."""

    def chat_model(
        self, tier: ModelTier = "primary", reasoning_effort: ReasoningEffort | None = None
    ) -> BaseChatModel:
        return get_chat_model(tier, reasoning_effort)

    def model_name(self, tier: ModelTier) -> str:
        return model_for(tier)

    def vision_model(self) -> BaseChatModel:
        return get_vision_model()

    def vision_model_name(self) -> str:
        return settings.llm_model_vision


def get_llm_provider() -> LLMProvider:
    """FastAPI dependency."""
    return LLMProvider()
