"""Unit tests for pure helpers: SQL validation, token usage, cost, tracing setup."""

import os
from decimal import Decimal

from langchain_core.messages import AIMessage

from app.core.config import ModelPrice, Settings, settings
from app.core.tracing import configure_tracing
from app.llm.usage import estimate_cost_usd, usage_from_message
from app.schemas.llm import TokenUsage
from app.sql_tools.validation import to_sqlglot_dialect, validate_sql

# --- SQL validation --------------------------------------------------------


def test_valid_select():
    result = validate_sql("SELECT dept, AVG(salary) FROM emp GROUP BY dept", "PostgreSQL")
    assert result.valid and result.statement_types == ["SELECT"] and result.dialect == "postgres"


def test_syntax_error_reports_position():
    result = validate_sql("SELECT name FROM users WHERE (age > 3", "MySQL")
    assert not result.valid
    assert result.errors == ["Line 1, column 37: Expecting )"]


def test_multiple_statements_and_types():
    sql = "-- note\nSELECT 1;\nCREATE INDEX ix ON orders (customer_id);"
    assert validate_sql(sql, "PostgreSQL").statement_types == ["SELECT", "CREATE"]


def test_blank_and_unterminated_input_are_invalid():
    assert validate_sql("   ", "MySQL").errors == ["No SQL statement found."]
    assert not validate_sql("SELECT 'abc", "PostgreSQL").valid


def test_dialect_labels_map_to_sqlglot_names():
    assert to_sqlglot_dialect("SQL Server") == "tsql"
    assert to_sqlglot_dialect("Spark SQL") == "spark"
    assert to_sqlglot_dialect("Unknown DB") is None  # generic SQL fallback


# --- Token usage and cost -------------------------------------------------


def test_usage_from_message_reads_reasoning_and_cache():
    message = AIMessage(
        content="",
        usage_metadata={
            "input_tokens": 1000,
            "output_tokens": 500,
            "total_tokens": 1500,
            "output_token_details": {"reasoning": 200},
            "input_token_details": {"cache_read": 400},
        },
    )
    usage = usage_from_message(message)
    assert (usage.reasoning_tokens, usage.cached_input_tokens) == (200, 400)
    assert usage_from_message(AIMessage(content="")) is None


def test_cost_uses_cached_and_output_prices(monkeypatch):
    monkeypatch.setitem(
        settings.llm_prices, "m", ModelPrice(input=0.15, output=0.60, cached_input=0.075)
    )
    usage = TokenUsage(
        input_tokens=1000, output_tokens=500, total_tokens=1500, cached_input_tokens=400
    )
    # 600 uncached * 0.15 + 400 cached * 0.075 + 500 output * 0.60, per million tokens
    assert estimate_cost_usd("m", usage) == Decimal("0.00042000")


def test_cost_unknown_model_or_usage_is_none():
    usage = TokenUsage(input_tokens=1, output_tokens=1, total_tokens=2)
    assert estimate_cost_usd("no-such-model", usage) is None
    assert estimate_cost_usd("openai/gpt-oss-120b", None) is None


# --- Tracing setup ---------------------------------------------------------


def make_settings(**overrides) -> Settings:
    # langsmith_api_key=None by default here, even if the developer's shell sets one.
    values = {"langsmith_api_key": None, **overrides}
    return Settings(_env_file=None, jwt_secret_key="x" * 40, groq_api_key="k", **values)


def test_tracing_off_by_default():
    env: dict[str, str] = {}
    assert configure_tracing(make_settings(langsmith_tracing=False), env) is False
    assert env == {}


def test_tracing_needs_an_api_key():
    env: dict[str, str] = {}
    assert configure_tracing(make_settings(langsmith_tracing=True), env) is False
    # A blank "LANGSMITH_API_KEY=" line in .env arrives as an empty string, not None.
    blank_key = make_settings(langsmith_tracing=True, langsmith_api_key=" ")
    assert configure_tracing(blank_key, env) is False
    assert env == {}


def test_tracing_exports_langsmith_env():
    env: dict[str, str] = {}
    enabled = configure_tracing(
        make_settings(langsmith_tracing=True, langsmith_api_key="lsv2_test", langsmith_project="p"),
        env,
    )
    assert enabled is True
    assert env == {
        "LANGSMITH_TRACING": "true",
        "LANGSMITH_API_KEY": "lsv2_test",
        "LANGSMITH_PROJECT": "p",
    }


def test_test_suite_never_traces():
    # conftest.py forces tracing off; nothing above may have switched it on globally.
    assert os.environ.get("LANGSMITH_TRACING") == "false"
