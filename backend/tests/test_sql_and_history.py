from langchain_core.language_models.fake_chat_models import FakeListChatModel

from app.llm.client import get_primary_llm
from app.llm.parsers import extract_sql
from app.main import app
from tests.conftest import signup_and_login


def test_extract_sql_unwraps_markdown_fence():
    assert extract_sql("```sql\nSELECT 1;\n```") == "SELECT 1;"
    assert extract_sql("SELECT 1;") == "SELECT 1;"


async def test_generate_requires_auth(client):
    res = await client.post("/api/v1/sql/generate", json={"question": "count users"})
    assert res.status_code == 401


async def test_generate_returns_clean_sql_and_saves_history(client):
    _, headers = await signup_and_login(client)
    res = await client.post(
        "/api/v1/sql/generate",
        json={"question": "list user emails", "dialect": "PostgreSQL"},
        headers=headers,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["output"] == "SELECT id, email FROM users;"
    assert body["history_id"]

    history = (await client.get("/api/v1/history", headers=headers)).json()
    assert history["total"] == 1
    assert history["items"][0]["tool"] == "generate"
    assert history["items"][0]["input_text"] == "list user emails"


async def test_save_history_false_skips_history(client):
    _, headers = await signup_and_login(client)
    await client.post(
        "/api/v1/sql/generate",
        json={"question": "list user emails", "save_history": False},
        headers=headers,
    )
    history = (await client.get("/api/v1/history", headers=headers)).json()
    assert history["total"] == 0


async def test_assist_rejects_unknown_mode(client):
    _, headers = await signup_and_login(client)
    res = await client.post(
        "/api/v1/sql/assist", json={"mode": "hack", "sql": "SELECT 1"}, headers=headers
    )
    assert res.status_code == 422


async def test_llm_failure_returns_502(client):
    class BrokenLLM(FakeListChatModel):
        async def _agenerate(self, *args, **kwargs):
            raise ConnectionError("groq down")

    app.dependency_overrides[get_primary_llm] = lambda: BrokenLLM(responses=["x"])
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
