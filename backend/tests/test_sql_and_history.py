from app.llm.output_schemas import SQLAnswer
from app.llm.parsers import extract_sql
from tests.conftest import connection_error, signup_and_login


def test_extract_sql_unwraps_markdown_fence():
    assert extract_sql("```sql\nSELECT 1;\n```") == "SELECT 1;"
    assert extract_sql("SELECT 1;") == "SELECT 1;"


async def test_generate_requires_auth(client):
    res = await client.post("/api/v1/sql/generate", json={"question": "count users"})
    assert res.status_code == 401


async def test_generate_returns_structured_validated_answer(client):
    _, headers = await signup_and_login(client)
    res = await client.post(
        "/api/v1/sql/generate",
        json={"question": "list user emails", "dialect": "PostgreSQL"},
        headers=headers,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["output"] == "SELECT id, email FROM users;"  # fences stripped
    assert body["explanation"] == "Lists every user's id and email."
    assert body["assumptions"] == ["The table is called users."]
    assert body["tables_used"] == ["users"]
    assert body["validation"] == {
        "valid": True,
        "dialect": "postgres",
        "statement_types": ["SELECT"],
        "errors": [],
    }
    assert body["prompt_version"] == "generate_sql@v2"
    assert body["usage"]["reasoning_tokens"] == 30
    assert body["model"] == "fake-primary"
    assert body["fallback_used"] is False
    assert body["history_id"]


async def test_history_records_usage_and_details(client):
    _, headers = await signup_and_login(client)
    await client.post(
        "/api/v1/sql/generate", json={"question": "list user emails"}, headers=headers
    )
    item = (await client.get("/api/v1/history", headers=headers)).json()["items"][0]
    assert item["tool"] == "generate"
    assert item["prompt_version"] == "generate_sql@v2"
    assert (item["input_tokens"], item["output_tokens"], item["reasoning_tokens"]) == (120, 80, 30)
    assert item["details"]["tables_used"] == ["users"]
    assert item["details"]["validation"]["valid"] is True


async def test_invalid_sql_from_model_is_flagged_not_hidden(client, fake_llm):
    fake_llm.models["primary"].answer = SQLAnswer(
        sql="SELEC id FROM users", explanation="x", assumptions=[], tables_used=["users"]
    )
    _, headers = await signup_and_login(client)
    res = await client.post("/api/v1/sql/generate", json={"question": "ids"}, headers=headers)
    assert res.status_code == 200
    validation = res.json()["validation"]
    assert validation["valid"] is False
    assert validation["errors"][0].startswith("Line 1, column")


async def test_unparseable_structured_output_returns_502(client, fake_llm):
    fake_llm.models["primary"].answer = None
    _, headers = await signup_and_login(client)
    res = await client.post("/api/v1/sql/generate", json={"question": "ids"}, headers=headers)
    assert res.status_code == 502
    assert res.json()["error"]["code"] == "llm_unavailable"


async def test_reasoning_effort_is_passed_to_the_model(client, fake_llm):
    _, headers = await signup_and_login(client)
    res = await client.post(
        "/api/v1/sql/generate",
        json={"question": "list user emails", "reasoning_effort": "low"},
        headers=headers,
    )
    assert res.json()["reasoning_effort"] == "low"
    assert set(fake_llm.efforts) == {"low"}


async def test_default_reasoning_effort_comes_from_settings(client):
    _, headers = await signup_and_login(client)
    res = await client.post("/api/v1/sql/generate", json={"question": "ids"}, headers=headers)
    assert res.json()["reasoning_effort"] == "medium"


async def test_explain_defaults_to_low_effort_but_request_can_override(client):
    _, headers = await signup_and_login(client)
    body = {"mode": "explain", "sql": "SELECT 1"}
    res = await client.post("/api/v1/sql/assist", json=body, headers=headers)
    assert res.json()["reasoning_effort"] == "low"  # the explain prompt's own default
    body["reasoning_effort"] = "high"
    res = await client.post("/api/v1/sql/assist", json=body, headers=headers)
    assert res.json()["reasoning_effort"] == "high"


async def test_invalid_reasoning_effort_rejected(client):
    _, headers = await signup_and_login(client)
    res = await client.post(
        "/api/v1/sql/generate",
        json={"question": "ids", "reasoning_effort": "extreme"},
        headers=headers,
    )
    assert res.status_code == 422


async def test_save_history_false_skips_history(client):
    _, headers = await signup_and_login(client)
    await client.post(
        "/api/v1/sql/generate",
        json={"question": "list user emails", "save_history": False},
        headers=headers,
    )
    history = (await client.get("/api/v1/history", headers=headers)).json()
    assert history["total"] == 0


async def test_assist_debug_uses_structured_output(client):
    _, headers = await signup_and_login(client)
    res = await client.post(
        "/api/v1/sql/assist",
        json={"mode": "debug", "sql": "SELEC id FROM users", "dialect": "MySQL"},
        headers=headers,
    )
    body = res.json()
    assert res.status_code == 200
    assert body["prompt_version"] == "debug_sql@v2"
    assert body["validation"]["dialect"] == "mysql"


async def test_assist_explain_returns_text_from_fast_model(client):
    _, headers = await signup_and_login(client)
    res = await client.post(
        "/api/v1/sql/assist",
        json={"mode": "explain", "sql": "SELECT dept, COUNT(*) FROM emp GROUP BY dept"},
        headers=headers,
    )
    body = res.json()
    assert body["output"] == "Counts rows per department and keeps the large ones."
    assert body["validation"] is None
    assert body["model"] == "fake-fast"


async def test_assist_rejects_unknown_mode(client):
    _, headers = await signup_and_login(client)
    res = await client.post(
        "/api/v1/sql/assist", json={"mode": "hack", "sql": "SELECT 1"}, headers=headers
    )
    assert res.status_code == 422


async def test_persistent_llm_failure_returns_502(client, fake_llm):
    # 3 connection errors = first try + 2 retries (LLM_MAX_RETRIES=2): all fail.
    fake_llm.models["primary"].errors = [connection_error() for _ in range(3)]
    _, headers = await signup_and_login(client)
    res = await client.post(
        "/api/v1/sql/assist", json={"mode": "debug", "sql": "SELEC 1"}, headers=headers
    )
    assert res.status_code == 502
    assert res.json()["error"]["code"] == "llm_unavailable"


async def test_history_is_isolated_between_users(client):
    _, alice = await signup_and_login(client, "alice@example.com")
    _, bob = await signup_and_login(client, "bob@example.com")
    created = await client.post(
        "/api/v1/sql/generate", json={"question": "alice private question"}, headers=alice
    )
    entry_id = created.json()["history_id"]

    assert (await client.get("/api/v1/history", headers=bob)).json()["total"] == 0
    stolen = await client.delete(f"/api/v1/history/{entry_id}", headers=bob)
    assert stolen.status_code == 404  # bob cannot delete (or even confirm) alice's entry

    own = await client.delete(f"/api/v1/history/{entry_id}", headers=alice)
    assert own.status_code == 204
