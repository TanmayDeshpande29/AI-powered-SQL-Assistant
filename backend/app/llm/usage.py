"""Token accounting and cost estimation.

LangChain normalizes every provider's token counts into AIMessage.usage_metadata:
  {"input_tokens": 286, "output_tokens": 298, "total_tokens": 584,
   "output_token_details": {"reasoning": 113}, "input_token_details": {"cache_read": 0}}
Reasoning tokens are already included in output_tokens (and billed at the output price).
"""

from decimal import Decimal

from langchain_core.messages import BaseMessage

from app.core.config import settings
from app.schemas.llm import TokenUsage

ONE_MILLION = Decimal(1_000_000)
USD_PRECISION = Decimal("0.00000001")  # 8 decimals: single requests cost fractions of a cent


def usage_from_message(message: BaseMessage | None) -> TokenUsage | None:
    meta = getattr(message, "usage_metadata", None)
    if not meta:
        return None
    output_details = meta.get("output_token_details") or {}
    input_details = meta.get("input_token_details") or {}
    return TokenUsage(
        input_tokens=meta["input_tokens"],
        output_tokens=meta["output_tokens"],
        total_tokens=meta["total_tokens"],
        reasoning_tokens=output_details.get("reasoning") or 0,
        cached_input_tokens=input_details.get("cache_read") or 0,
    )


def estimate_cost_usd(model: str, usage: TokenUsage | None) -> Decimal | None:
    """List-price cost of one call. Decimal, not float: binary floats can't represent
    most decimal fractions exactly, and money must add up exactly."""
    price = settings.llm_prices.get(model)
    if usage is None or price is None:
        return None
    cached = min(usage.cached_input_tokens, usage.input_tokens)
    cached_price = price.cached_input if price.cached_input is not None else price.input
    total = (
        Decimal(usage.input_tokens - cached) * Decimal(str(price.input))
        + Decimal(cached) * Decimal(str(cached_price))
        + Decimal(usage.output_tokens) * Decimal(str(price.output))
    ) / ONE_MILLION
    return total.quantize(USD_PRECISION)
