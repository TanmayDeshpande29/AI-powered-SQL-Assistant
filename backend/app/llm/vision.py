"""Reading database schemas from screenshots with a vision (multimodal) LLM.

A two-stage pipeline:
  1. perception  - the vision model transcribes the image into CREATE TABLE text
  2. parsing     - our deterministic DDL parser (app/sql_tools/ddl.py) reads that text
Asking for DDL rather than JSON keeps one parser for every input kind, and the
transcription stays human-readable: the user can see exactly what the model "read".
"""

import base64
import logging
import time
from dataclasses import dataclass

from langchain_core.prompts import ChatPromptTemplate

from app.core.exceptions import LLMServiceError, RateLimitedError
from app.llm.client import RATE_LIMIT_ERRORS, LLMProvider, retry_after_seconds, with_resilience
from app.llm.parsers import extract_sql
from app.llm.prompts import PromptSpec
from app.llm.usage import estimate_cost_usd, usage_from_message
from app.schemas.llm import TokenUsage

logger = logging.getLogger(__name__)

TRANSCRIBE_SCHEMA_IMAGE = PromptSpec(
    name="transcribe_schema_image",
    version=1,
    template=ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You transcribe images of database schemas (ER diagrams, table designers, "
                "column lists, screenshots of DDL) into {dialect} SQL. Output only CREATE TABLE "
                "statements, in one ```sql block: every table and column you can read, the data "
                "types as shown, PRIMARY KEY, UNIQUE and NOT NULL where the image shows them, "
                "and FOREIGN KEY ... REFERENCES for every relationship that is drawn or labelled. "
                "Never invent tables, columns or types that are not visible. If no schema is "
                "visible, output an empty ```sql block.",
            ),
            (
                "human",
                [
                    {"type": "text", "text": "Transcribe the schema in this image."},
                    {"type": "image_url", "image_url": {"url": "{image_url}"}},
                ],
            ),
        ]
    ),
)


@dataclass(frozen=True)
class Transcription:
    sql: str
    model: str
    latency_ms: int
    usage: TokenUsage | None
    cost_usd: float | None


async def transcribe_schema_image(
    provider: LLMProvider, image: bytes, content_type: str, dialect: str
) -> Transcription:
    # Images travel inside the JSON request as a base64 "data URL".
    image_url = f"data:{content_type};base64,{base64.b64encode(image).decode()}"
    chain = TRANSCRIBE_SCHEMA_IMAGE.template | with_resilience(provider.vision_model())
    started = time.perf_counter()
    try:
        message = await chain.ainvoke(
            {"dialect": dialect, "image_url": image_url},
            config={"run_name": TRANSCRIBE_SCHEMA_IMAGE.name, "tags": [TRANSCRIBE_SCHEMA_IMAGE.id]},
        )
    except RATE_LIMIT_ERRORS as exc:  # only one vision model: nothing to fall back to
        raise RateLimitedError(retry_after_seconds(exc)) from exc
    except Exception as exc:
        logger.exception("Vision transcription failed")
        raise LLMServiceError("The vision model could not read the image.") from exc

    text = message.content if isinstance(message.content, str) else ""
    model = message.response_metadata.get("model_name") or provider.vision_model_name()
    usage = usage_from_message(message)
    cost = estimate_cost_usd(model, usage)
    return Transcription(
        sql=extract_sql(text),
        model=model,
        latency_ms=int((time.perf_counter() - started) * 1000),
        usage=usage,
        cost_usd=float(cost) if cost is not None else None,
    )
