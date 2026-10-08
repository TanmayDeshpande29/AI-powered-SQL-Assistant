"""Prompt templates, each with a name and a version.

ChatPromptTemplate builds a list of role-tagged messages:
  system -> the model's standing instructions (persona, rules)
  human  -> this request's data, injected through {placeholders}
Placeholders are filled by LangChain, never by f-strings, so user text cannot break
the template. User-supplied text is wrapped in <request>/<sql> tags so the model can
tell data from instructions (basic prompt-injection hygiene).

Every LLM call records `spec.id` (e.g. "generate_sql@v2") in history and traces, so
Phase 5 evaluations can compare prompt versions. Change a prompt's wording -> bump
its version.
"""

from dataclasses import dataclass

from langchain_core.prompts import ChatPromptTemplate

from app.core.config import ReasoningEffort


@dataclass(frozen=True)
class PromptSpec:
    name: str
    version: int
    template: ChatPromptTemplate
    # Used when the request doesn't choose one; None -> settings.llm_reasoning_effort.
    default_reasoning_effort: ReasoningEffort | None = None

    @property
    def id(self) -> str:
        return f"{self.name}@v{self.version}"


# v1 (Phase 0) asked for "SQL only" as plain text. v2 asks for the SQLAnswer fields.
GENERATE_SQL = PromptSpec(
    name="generate_sql",
    version=2,
    template=ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a senior data engineer who writes correct, efficient {dialect} SQL. "
                "The user's database schema is not available yet, so infer conventional "
                "table and column names from the request, keep them simple, and record "
                "every such guess in `assumptions`. List each table the query touches in "
                "`tables_used`. Keep `explanation` to one to three sentences.",
            ),
            (
                "human",
                "Write a {dialect} query for the request between the <request> tags.\n"
                "<request>\n{question}\n</request>",
            ),
        ]
    ),
)

DEBUG_SQL = PromptSpec(
    name="debug_sql",
    version=2,
    template=ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a senior {dialect} developer. Find every syntax and logic error in "
                "the user's query and put the corrected query in `sql`. In `explanation`, "
                "list each fix briefly. Record guesses about intent or schema in "
                "`assumptions` and list every table in `tables_used`.",
            ),
            ("human", "Debug this {dialect} query:\n<sql>\n{sql}\n</sql>"),
        ]
    ),
)

OPTIMIZE_SQL = PromptSpec(
    name="optimize_sql",
    version=2,
    template=ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a {dialect} performance expert. Rewrite the user's query to return "
                "the same result more efficiently: sargable predicates (no functions on "
                "indexed columns), no SELECT *, no needless subqueries or DISTINCT. Put the "
                "rewritten query in `sql`. In `explanation`, summarize each change and "
                "suggest helpful indexes as CREATE INDEX statements. List every table in "
                "`tables_used`.",
            ),
            ("human", "Optimize this {dialect} query:\n<sql>\n{sql}\n</sql>"),
        ]
    ),
)

# Streamed as plain markdown for a person to read, so no output schema.
# Low reasoning effort: describing a query needs little "thinking", and reasoning tokens
# are generated BEFORE the first visible word. Measured with gpt-oss-20b: at medium
# effort 71% of the output was hidden reasoning and the first word took 1.7 s.
EXPLAIN_SQL = PromptSpec(
    name="explain_sql",
    version=2,
    default_reasoning_effort="low",
    template=ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a patient SQL teacher. Explain what the user's {dialect} query "
                "does in plain English using short markdown: a one-line summary, then one "
                "bullet per clause (FROM/JOIN, WHERE, GROUP BY, ...), then any pitfalls "
                "you notice.",
            ),
            ("human", "Explain this {dialect} query:\n<sql>\n{sql}\n</sql>"),
        ]
    ),
)

STRUCTURED_PROMPTS = {"generate": GENERATE_SQL, "debug": DEBUG_SQL, "optimize": OPTIMIZE_SQL}
