"""Server-Sent Events endpoint: POST /api/v1/sql/explain/stream."""

import json

from tests.conftest import FAKE_EXPLANATION, rate_limit_error, signup_and_login

URL = "/api/v1/sql/explain/stream"
BODY = {"sql": "SELECT dept, COUNT(*) FROM emp GROUP BY dept", "dialect": "MySQL"}


def parse_sse(text: str) -> list[tuple[str, dict]]:
    """Turn a text/event-stream body into [(event, data), ...]."""
    events = []
    for block in text.strip().split("\n\n"):
        event, data = "message", []
        for line in block.splitlines():
            if line.startswith("event:"):
                event = line[len("event:") :].strip()
            elif line.startswith("data:"):
                data.append(line[len("data:") :].strip())
        if data:
            events.append((event, json.loads("\n".join(data))))
    return events


async def test_stream_sends_tokens_then_done(client):
    _, headers = await signup_and_login(client)
    res = await client.post(URL, json=BODY, headers=headers)
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/event-stream")

    events = parse_sse(res.text)
    names = [name for name, _ in events]
    assert names[-1] == "done"
    assert set(names[:-1]) == {"token"} and len(names) > 2  # several chunks, not one blob
    streamed = "".join(data["text"] for name, data in events if name == "token")
    assert streamed == FAKE_EXPLANATION

    done = events[-1][1]
    assert done["output"] == FAKE_EXPLANATION
    assert done["prompt_version"] == "explain_sql@v3"
    assert done["usage"]["total_tokens"] == 200
    assert done["history_id"]

    history = (await client.get("/api/v1/history", headers=headers)).json()
    assert history["items"][0]["tool"] == "explain"


async def test_stream_requires_auth_before_streaming(client):
    res = await client.post(URL, json=BODY)
    assert res.status_code == 401  # a normal JSON error, not an event stream
    assert res.json()["error"]["code"] == "not_authenticated"


async def test_stream_reports_failures_as_error_event(client, fake_llm):
    fake_llm.models["fast"].errors = [rate_limit_error("5")]
    fake_llm.models["primary"].errors = [rate_limit_error("9")]
    _, headers = await signup_and_login(client)
    res = await client.post(URL, json=BODY, headers=headers)
    assert res.status_code == 200  # headers were already sent when the error happened
    events = parse_sse(res.text)
    assert events == [
        (
            "error",
            {
                "code": "rate_limited",
                "message": "The AI service is busy (rate limit reached). Try again in 5 s.",
                "details": {"retry_after": 5},
            },
        )
    ]
