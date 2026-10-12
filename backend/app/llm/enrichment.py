"""LLM-written descriptions and synonyms for tables (document expansion for search).

One structured call describes a batch of tables: the fast model fills TableDescriptions
(strict JSON schema), with the primary model as its fallback on rate limits.
"""

import logging
import time
from dataclasses import dataclass

from app.core.config import settings
from app.core.exceptions import LLMServiceError, RateLimitedError
from app.llm.client import RATE_LIMIT_ERRORS, LLMProvider, retry_after_seconds, with_resilience
from app.llm.output_schemas import TableDescription, TableDescriptions
from app.llm.prompts import DESCRIBE_TABLES
from app.llm.usage import estimate_cost_usd, usage_from_message

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Enrichment:
    descriptions: list[TableDescription]
    model: str
    latency_ms: int
    cost_usd: float | None


async def describe_tables(provider: LLMProvider, cards: list[str]) -> Enrichment:
    """Describe the tables whose cards (render_table_card text) are given."""
    effort = DESCRIBE_TABLES.default_reasoning_effort

    def structured(tier):
        return provider.chat_model(tier, effort).with_structured_output(
            TableDescriptions,
            method=settings.llm_structured_output_method,
            strict=True,
            include_raw=True,
        )

    chain = DESCRIBE_TABLES.template | with_resilience(
        structured("fast"), fallback=structured("primary")
    )
    started = time.perf_counter()
    try:
        result = await chain.ainvoke(
            {"tables": "\n\n".join(cards)},
            config={"run_name": DESCRIBE_TABLES.name, "tags": [DESCRIBE_TABLES.id]},
        )
    except RATE_LIMIT_ERRORS as exc:
        raise RateLimitedError(retry_after_seconds(exc)) from exc
    except Exception as exc:
        logger.exception("Describing tables failed")
        raise LLMServiceError("The language model could not describe the tables.") from exc

    parsed: TableDescriptions | None = result["parsed"]
    if parsed is None:
        raise LLMServiceError("The table descriptions did not match the expected format.")
    raw = result["raw"]
    model = raw.response_metadata.get("model_name") or provider.model_name("fast")
    cost = estimate_cost_usd(model, usage_from_message(raw))
    return Enrichment(
        descriptions=parsed.tables,
        model=model,
        latency_ms=int((time.perf_counter() - started) * 1000),
        cost_usd=float(cost) if cost is not None else None,
    )
