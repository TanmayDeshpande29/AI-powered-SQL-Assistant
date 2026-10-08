"""Retries for transient errors, fallbacks for rate limits (app/llm/client.py)."""

from app.llm.client import retry_after_seconds
from tests.conftest import connection_error, rate_limit_error, signup_and_login


def test_retry_after_seconds_reads_header():
    assert retry_after_seconds(rate_limit_error("7")) == 7
    assert retry_after_seconds(rate_limit_error("0.3")) == 1  # never advertise 0 s
    assert retry_after_seconds(rate_limit_error("Wed, 21 Oct 2026 07:28:00 GMT")) is None
    assert retry_after_seconds(ValueError("no response")) is None


async def test_transient_error_is_retried_on_same_model(client, fake_llm):
    fake_llm.models["primary"].errors = [connection_error()]  # fails once, then works
    _, headers = await signup_and_login(client)
    res = await client.post("/api/v1/sql/generate", json={"question": "ids"}, headers=headers)
    assert res.status_code == 200
    assert res.json()["model"] == "fake-primary"
    assert fake_llm.models["primary"].calls == 2
    assert fake_llm.models["fast"].calls == 0


async def test_rate_limit_falls_back_to_other_model_without_retrying(client, fake_llm):
    fake_llm.models["primary"].errors = [rate_limit_error()]
    _, headers = await signup_and_login(client)
    res = await client.post("/api/v1/sql/generate", json={"question": "ids"}, headers=headers)
    body = res.json()
    assert res.status_code == 200
    assert body["model"] == "fake-fast"
    assert body["fallback_used"] is True
    assert fake_llm.models["primary"].calls == 1  # no retry against a rate limit


async def test_both_models_rate_limited_returns_429_with_retry_after(client, fake_llm):
    fake_llm.models["primary"].errors = [rate_limit_error("12")]
    fake_llm.models["fast"].errors = [rate_limit_error("3")]
    _, headers = await signup_and_login(client)
    res = await client.post("/api/v1/sql/generate", json={"question": "ids"}, headers=headers)
    assert res.status_code == 429
    assert res.headers["retry-after"] == "12"  # from the primary's (first) error
    assert res.json()["error"]["code"] == "rate_limited"
    assert res.json()["error"]["details"] == {"retry_after": 12}
