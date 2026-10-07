"""SQL generation and assistance, implemented as LangChain (LCEL) chains.

A chain is `prompt | llm | parser`: each step's output is the next step's input.
    ChatPromptTemplate --(messages)--> ChatGroq --(AIMessage)--> StrOutputParser --> str
Phase 2+ will insert a retriever in front of the prompt (that is RAG), and Phase 6
replaces this module with a LangGraph agent graph.
"""

import logging
import time
from dataclasses import dataclass

from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from app.core.exceptions import LLMServiceError
from app.llm.client import model_name
from app.llm.parsers import extract_sql
from app.llm.prompts import ASSIST_PROMPTS, GENERATE_SQL_PROMPT
from app.schemas.sql import AssistMode

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LLMResult:
    output: str
    model: str
    latency_ms: int


async def _run_chain(prompt: ChatPromptTemplate, llm: BaseChatModel, inputs: dict) -> LLMResult:
    chain = prompt | llm | StrOutputParser()
    started = time.perf_counter()
    try:
        text = await chain.ainvoke(inputs)  # async: the event loop keeps serving other users
    except Exception as exc:  # network errors, 429 after retries, auth errors...
        logger.exception("LLM call failed")
        raise LLMServiceError() from exc
    latency_ms = int((time.perf_counter() - started) * 1000)

    if not text.strip():
        raise LLMServiceError("The language model returned an empty response.")
    return LLMResult(output=text.strip(), model=model_name(llm), latency_ms=latency_ms)


async def generate_sql(llm: BaseChatModel, *, question: str, dialect: str) -> LLMResult:
    result = await _run_chain(GENERATE_SQL_PROMPT, llm, {"question": question, "dialect": dialect})
    return LLMResult(extract_sql(result.output), result.model, result.latency_ms)


async def assist_sql(llm: BaseChatModel, *, mode: AssistMode, sql: str, dialect: str) -> LLMResult:
    result = await _run_chain(ASSIST_PROMPTS[mode], llm, {"sql": sql, "dialect": dialect})
    if mode == "explain":  # explanations are markdown prose, keep them as-is
        return result
    return LLMResult(extract_sql(result.output), result.model, result.latency_ms)
