"""Prompt templates. Kept apart from code so they can be versioned and evaluated.

ChatPromptTemplate builds a list of role-tagged messages:
  system -> the model's standing instructions (persona, rules, output format)
  human  -> this request's data, injected through {placeholders}
Placeholders are filled by LangChain, never by f-strings, so user text cannot
accidentally break the template.
"""

from langchain_core.prompts import ChatPromptTemplate

SQL_ONLY_RULES = (
    "Respond with SQL only: no prose, no markdown headings. "
    "If you must state an assumption, put it in a SQL comment (-- ...)."
)

GENERATE_SQL_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a senior data engineer who writes correct, efficient {dialect} SQL. "
            "No database schema is available yet, so infer conventional table and column "
            "names from the request and keep them simple. " + SQL_ONLY_RULES,
        ),
        ("human", "Write a {dialect} query for this request:\n\n{question}"),
    ]
)

DEBUG_SQL_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a senior {dialect} developer. Find every syntax and logic error in the "
            "user's query and return the corrected query. Mark each fix with a short "
            "-- comment on the line it changes. " + SQL_ONLY_RULES,
        ),
        ("human", "Debug this {dialect} query:\n\n{sql}"),
    ]
)

OPTIMIZE_SQL_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a {dialect} performance expert. Rewrite the user's query to return the "
            "same result more efficiently (sargable predicates, avoid SELECT *, needless "
            "subqueries, functions on indexed columns). Suggest helpful indexes as "
            "-- comments at the end. " + SQL_ONLY_RULES,
        ),
        ("human", "Optimize this {dialect} query:\n\n{sql}"),
    ]
)

EXPLAIN_SQL_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a patient SQL teacher. Explain what the user's {dialect} query does in "
            "plain English using short markdown: a one-line summary, then a bullet per "
            "clause (FROM/JOIN, WHERE, GROUP BY, ...), then any pitfalls you notice.",
        ),
        ("human", "Explain this {dialect} query:\n\n{sql}"),
    ]
)

ASSIST_PROMPTS = {
    "debug": DEBUG_SQL_PROMPT,
    "optimize": OPTIMIZE_SQL_PROMPT,
    "explain": EXPLAIN_SQL_PROMPT,
}
