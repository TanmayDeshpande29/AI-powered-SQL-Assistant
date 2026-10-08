# Phase 1: the LLM layer (deep dive)

> **Goal:** every LLM call becomes *structured, validated, streamed, measured, resilient and traceable*, so every later phase (RAG, evaluation, agents, MCP) builds on calls we can trust and inspect.
> **Status:** done on 2026-10-07 · 51 tests passing · verified live (API → PostgreSQL → Groq → browser UI).
> Concepts: notebook chapter 5 ([PDF](../notebook/SQLAssist-Notebook.pdf)). Previous phase: [Phase 0](phase-0-foundation.md).

---

## 0. TL;DR: what changed

| Area | Phase 0 | Phase 1 |
|---|---|---|
| Model output | free text, cleaned with a regex | **typed `SQLAnswer`** (sql, explanation, assumptions, tables_used) via strict JSON-schema decoding |
| Trust | none: whatever the model said | **sqlglot syntax validation** on every query: `valid`, `dialect`, `statement_types`, `errors` |
| Explanations | wait for the full answer | **streamed word by word** over Server-Sent Events |
| Visibility | model + latency | **tokens** (input / output / reasoning / cached), **list-price cost**, prompt version, effort, stored per request |
| Speed vs quality | fixed | **reasoning effort** per request (low / medium / high), with per-prompt defaults |
| Failures | SDK retried 429s silently (up to ~2 min) | **retry transient errors, fall back on rate limits**, `429 + Retry-After` when both tiers are limited |
| Prompts | unversioned strings | **`PromptSpec`** with name + version, recorded in history and traces |
| Debugging | logs only | **LangSmith tracing** (opt-in, configured at startup) |
| DB connections | held during the LLM call | **released** before slow LLM work |
| Tests | 23 | **51** |

---

## 1. What's new, at a glance

```
backend/app/
  core/config.py           + ReasoningEffort, ModelPrice, DEFAULT_LLM_PRICES, LLM + LangSmith settings
  core/tracing.py          NEW  export LangSmith settings into the environment at startup
  core/exceptions.py       + headers property, RateLimitedError (429 + Retry-After)
  llm/client.py            REWRITTEN  model tiers, retry/fallback policy, LLMProvider dependency
  llm/output_schemas.py    NEW  SQLAnswer: what the model must return
  llm/prompts.py           REWRITTEN  PromptSpec (name, version, default effort), v2 prompts
  llm/usage.py             NEW  token usage + cost estimation (Decimal)
  sql_tools/validation.py  NEW  sqlglot syntax validation, dialect mapping
  schemas/llm.py           NEW  TokenUsage, SQLValidation (API shapes)
  schemas/sql.py           + reasoning_effort on requests, ExplainSQLRequest, richer LLMResponse/history
  models/query_history.py  + 7 nullable columns (tokens, cost, prompt version, effort, details)
  services/sql.py          REWRITTEN  run_structured, stream_explanation, LLMResult
  services/history.py      record() stores the whole LLMResult
  db/session.py            + release_connection()
  api/deps.py              PrimaryLLM -> LLM (provider)
  api/v1/routes/sql.py     + POST /sql/explain/stream (SSE), connection release, richer responses
  main.py                  configure_tracing() at startup, version 0.2.0
backend/alembic/versions/2026_10_07_0002-...  migration 2
frontend/src/
  lib/api.js               authFetch + toApiError + SSE reader, streamExplain(), reasoningEffort
  components/ReasoningEffortSelect.jsx  NEW  "Thinking" switch
  components/LLMResultDetails.jsx       NEW  validation badge, explanation, assumptions, metrics
  queryBuilder.jsx         effort switch + result details; fixed the Examples crash
  sql_assistants.jsx       streaming explain, cancellation, result details
```

---

## 2. Libraries and features we started using

| Tool | Where | Why |
|---|---|---|
| `with_structured_output()` (LangChain) | `services/sql.py` | turns a Pydantic class into a JSON Schema the model must follow, and parses the reply back into that class |
| Groq **strict** structured outputs | via `method="json_schema", strict=True` | **constrained decoding**: tokens that would break the schema are never sampled, so the reply always parses (gpt-oss models only) |
| `Runnable.with_retry()` | `llm/client.py` | retries chosen exception types with exponential backoff + jitter (built on the `tenacity` library) |
| `Runnable.with_fallbacks()` | `llm/client.py` | if the first runnable raises a handled exception, run the next one |
| `chain.astream()` | `services/sql.py` | yields `AIMessageChunk`s as the model produces them |
| `fastapi.sse` (`EventSourceResponse`, `ServerSentEvent`) | `routes/sql.py` | native SSE in FastAPI ≥ 0.135: a path operation that `yield`s events; keep-alive pings built in |
| **sqlglot** (new dependency) | `sql_tools/validation.py` | pure-Python SQL parser/transpiler for 20+ dialects; produces an AST |
| **LangSmith** (`langsmith`, ships with langchain-core) | `core/tracing.py` | records every chain/LLM call as a trace when two env vars are set |
| `ReadableStream` + `TextDecoderStream` (browser) | `lib/api.js` | read a streaming HTTP response chunk by chunk |
| `AbortController` (browser) | `sql_assistants.jsx` | cancel an in-flight request or stream |

---

## 3. Backend, file by file

### 3.1 `core/config.py`: new settings
- `ReasoningEffort = Literal["low", "medium", "high"]` is one shared type for requests, settings and prompts.
- `ModelPrice(input, output, cached_input)` holds USD per **1 million** tokens. `DEFAULT_LLM_PRICES` are Groq's list prices checked on 2026-10-07:
  - gpt-oss-120b: $0.15 / $0.60 / $0.075
  - gpt-oss-20b: $0.075 / $0.30 / $0.037
  
  You can override them with `LLM_PRICES` (JSON) in `.env`.
- `llm_reasoning_effort` is the global default.
- `llm_max_output_tokens = 4096` is a hard cap per answer. It bounds cost and latency, and **reasoning tokens count toward it**.
- `llm_structured_output_method`: `json_schema` (constrained) or `function_calling` (schema sent as a tool definition).
- `llm_max_retries` now means **retries for transient errors only** (see 3.4).
- The `langsmith_*` settings are read from `.env` like everything else.

### 3.2 `core/tracing.py` (new): LangSmith setup
LangChain traces automatically when the LangSmith SDK sees `LANGSMITH_TRACING=true` and `LANGSMITH_API_KEY` in the **process environment**. pydantic-settings reads `.env` *without exporting* it to `os.environ`, so `configure_tracing()` copies the values over once at startup (called from the lifespan in `main.py`).
- **Gotcha 1:** `langsmith.utils.get_env_var` is wrapped in `functools.lru_cache`, so the first read is cached for the life of the process. We confirmed that importing the app only reads two compression settings, so configuring in the lifespan (before any LLM call) is early enough.
- **Gotcha 2:** a blank `LANGSMITH_API_KEY=` line loads as `""`, not `None`. Both are treated as "missing".
- The `environ` parameter defaults to `os.environ`, but tests pass a plain `dict`. An earlier version of the test changed the real environment and leaked `LANGSMITH_TRACING=true` into later tests.

### 3.3 `core/exceptions.py`: errors that carry headers
- `AppError.headers` is a property returning extra response headers (`None` by default). The handler sends them with the JSON envelope.
- `AuthenticationError.headers` returns `WWW-Authenticate: Bearer`, which the 401 spec requires. This was moved here from a special case in the handler.
- `RateLimitedError(retry_after)` is a **429** with code `rate_limited`, a human message ("Try again in 12 s."), `details.retry_after`, and the standard **`Retry-After`** header.

### 3.4 `llm/client.py`: tiers and the resilience policy
- **Two tiers.** `primary` (gpt-oss-120b) writes SQL; `fast` (gpt-oss-20b) explains. `model_for(tier)` and `other_tier(tier)` map between them.
- `get_chat_model(tier, reasoning_effort)` is `@lru_cache`d, so there are at most 6 `ChatGroq` instances, reused across requests. Each sets `temperature`, `timeout`, `max_tokens`, `reasoning_effort`, and **`max_retries=0`**.
- **Why `max_retries=0`?** We read the Groq SDK source (`_calculate_retry_timeout`). On a 429 it sleeps for the server's `Retry-After`, if that is ≤ 60 s, and retries up to `max_retries` times. With the old setting of 2, a rate-limited request could hang for about two minutes before any of our code ran.
- **`with_resilience(runnable, fallback)`** is the policy:
  - **Transient errors** (`groq.APIConnectionError`, which includes timeouts, and `groq.InternalServerError`, any 5xx): `with_retry(...)` retries the same model up to `llm_max_retries` times. The wait grows exponentially with random **jitter** (initial 0.5 s, capped at 4 s), so many clients that failed together don't all retry at the same instant (the "thundering herd").
  - **Rate limits** (`groq.RateLimitError`): `with_fallbacks([...], exceptions_to_handle=(RateLimitError,))` immediately switches to the other tier. Waiting would only make this user wait.
- `retry_after_seconds(exc)` reads the `retry-after` header from the exception's HTTP response. Fractions are rounded up to at least 1, and an HTTP-date value is treated as unknown.
- `LLMProvider.chat_model(tier, effort)` and `.model_name(tier)` are what services use. `get_llm_provider()` is the FastAPI dependency, and tests replace it with a fake provider.

### 3.5 `llm/output_schemas.py` (new): what the model must return
```python
class SQLAnswer(BaseModel):
    """SQL produced for the user's request, plus what a reviewer needs to trust it."""
    sql: str = Field(description="The complete SQL, ready to run. Plain SQL, no markdown fences.")
    explanation: str = Field(description="One to three sentences: ...")
    assumptions: list[str] = Field(description="Every guess about table names, column names ...")
    tables_used: list[str] = Field(description="Every table the SQL reads from or writes to.")
```
- This is **not** an API schema (those live in `app/schemas/`). It is a contract with the model: LangChain converts it to JSON Schema and sends it in the request.
- The **docstring and the field descriptions are part of that schema**, so they work as instructions to the model.
- Strict mode requires every field to be `required` and `additionalProperties: false`, so there are no defaults here. "No assumptions" is an empty list, not a missing field.

### 3.6 `llm/prompts.py`: versioned prompts
- `PromptSpec(name, version, template, default_reasoning_effort)` with `id` → `"generate_sql@v2"`.
  - The id goes into history, trace tags and metadata, so Phase 5 evaluations can compare `@v2` against `@v3`.
  - **Rule: change the wording → bump the version.**
- v2 prompts tell the model *what to put in which field*, e.g. "record every guess in `assumptions`". The schema itself takes care of the format.
- User text is wrapped in `<request>…</request>` or `<sql>…</sql>` tags. This helps the model tell **data** from **instructions**: basic prompt-injection hygiene, though not a complete defense (that's the Phase 6 Safety Guard).
- `EXPLAIN_SQL.default_reasoning_effort = "low"`, a decision based on measurement (see §6).

### 3.7 `llm/usage.py` (new): tokens and money
- `usage_from_message(msg)` reads LangChain's provider-neutral `AIMessage.usage_metadata`:
  - `input_tokens`, `output_tokens`, `total_tokens`
  - `output_token_details.reasoning` → **reasoning tokens**
  - `input_token_details.cache_read` → **cached prompt tokens**
- **Reasoning tokens are already included in `output_tokens`.** They are billed at the output price and count toward `max_tokens`.
- `estimate_cost_usd(model, usage)` = (uncached input × input price + cached input × cached price + output × output price) / 1,000,000.
- The result is a **`Decimal`** quantized to 8 places. Binary floats can't represent most decimal fractions exactly (`0.1 + 0.2 != 0.3`), and money must add up exactly.

### 3.8 `sql_tools/validation.py` (new): syntax checking with sqlglot
- sqlglot parses SQL into an **AST** (abstract syntax tree): typed nodes like `Select → From → Table`. If parsing fails, the SQL isn't valid for that dialect, and `ParseError.errors` tells us the line, column and reason.
- `DIALECT_ALIASES` maps the UI's labels to sqlglot dialect names ("SQL Server" → `tsql`, "Spark SQL" → `spark`, …). Unknown labels fall back to generic SQL.
- `validate_sql(sql, label)` returns `SQLValidation`:
  - `valid` and `dialect`;
  - `statement_types` from each AST root's `.key` (`SELECT`, `UNION`, `CREATE`, `DELETE`…);
  - up to 5 `errors`. `TokenError` covers e.g. an unterminated string.
- **Syntax ≠ semantics.** sqlglot doesn't know your tables, so `SELECT x FROM table_that_does_not_exist` still passes. Name checks come with schema ingestion (Phase 2) and the Validator agent (Phase 6). `statement_types` is already what the Safety Guard needs to block `DELETE`/`DROP`.

### 3.9 `schemas/llm.py` + `schemas/sql.py`
- `TokenUsage` and `SQLValidation` are API shapes shared by responses and history.
- The `_LLMRequest` base adds `dialect`, `save_history` and `reasoning_effort` (`None` means the server default) to `GenerateSQLRequest`, `AssistSQLRequest` and the new `ExplainSQLRequest`.
- `LLMResponse` keeps `output`, so the Phase 0 frontend still works, and adds:
  - `explanation`, `assumptions`, `tables_used`, `validation`
  - `prompt_version`, `reasoning_effort`, `usage`, `cost_usd`, `fallback_used`
- `QueryHistoryRead` exposes the new columns.

### 3.10 `models/query_history.py` + migration 2
- Seven new columns: `prompt_version`, `reasoning_effort`, `input_tokens`, `output_tokens`, `reasoning_tokens`, `cost_usd`, `details`. All are **nullable**, so rows written before the migration stay valid.
  - `cost_usd`: `Numeric(12, 8)`, exact decimal storage (the database twin of `Decimal`).
  - `details`: `JSON().with_variant(JSONB(), "postgresql")`. **JSONB** on PostgreSQL is stored as parsed binary, can be indexed (GIN) and queried (`details->'validation'->>'valid'`). Plain JSON is used on SQLite in the tests.
- This time the migration was **autogenerated against the real PostgreSQL** (your `.env` now has working credentials), so it came out dialect-correct. It was reviewed and reformatted, then verified with upgrade → `alembic check` → downgrade → upgrade → `alembic check`.

### 3.11 `services/sql.py`: two output styles
The module docstring states the rule: **structure what code consumes; stream what people read.**
- `LLMResult` is a frozen dataclass with everything a call produced, independent of HTTP.
- `_effort(spec, requested)` picks the request's choice, else the prompt's default, else the global default.
- `run_structured(provider, task, inputs, …)` handles generate, debug and optimize:
  1. `structured(tier)` = `chat_model(tier, effort).with_structured_output(SQLAnswer, method=…, strict=True, include_raw=True)`.
  2. `chain = template | with_resilience(structured("primary"), fallback=structured("fast"))`.
  3. `await chain.ainvoke(inputs, config=_run_config(...))`. The config names the run in traces and adds tags and metadata.
  4. Errors: a `RateLimitError` that escaped the fallback → `RateLimitedError` (429). Anything else → `LLMServiceError` (502, logged with traceback).
  5. `include_raw=True` returns `{"raw": AIMessage, "parsed": SQLAnswer | None, "parsing_error": …}`. We need **raw** for token usage and the answering model's name. If `parsed` is `None` → 502 "did not match the expected format".
  6. Post-processing:
     - `extract_sql` defensively strips fences;
     - assumptions and table names are trimmed;
     - `fallback_used = (answering model != primary)`, read from `raw.response_metadata["model_name"]`;
     - cost is estimated;
     - `validate_sql()` runs.
- `stream_explanation(...)` is an **async generator** that yields text pieces, then one final `LLMResult`.
  - It uses the **fast** tier, with the primary tier as its fallback.
  - `final = chunk if final is None else final + chunk` merges chunks: text concatenates, and usage (sent only on the last chunk) lands on `final`.
  - Chunks with no visible text (reasoning) are skipped.
  - Fallbacks only work **before the first chunk**: once text has been sent, we can't switch models mid-sentence. This matches LangChain's `RunnableWithFallbacks.astream`.
- `explain_sql()` (non-streamed) reuses the stream and keeps only the final result. `assist_sql()` routes explain to it and everything else to `run_structured`.

### 3.12 `services/history.py`
`record(db, user_id, tool, dialect, input_text, result)` now stores the whole `LLMResult`: tokens, cost, prompt version, effort, and `details` (explanation, assumptions, tables, validation, fallback flag).

### 3.13 `db/session.py`: `release_connection()`
`await session.commit()` ends the auth query's transaction and returns its connection to the pool *before* the LLM call. SQLAlchemy's default pool is 5 connections plus 10 overflow per process. Holding one for a 1–3 s LLM call means ~15 concurrent requests could exhaust it, even though the database sits idle. Objects stay readable (`expire_on_commit=False`), and the history insert later borrows a connection again.

### 3.14 `api/deps.py`
`PrimaryLLM` (one model instance) became **`LLM = Annotated[LLMProvider, Depends(get_llm_provider)]`**, a *factory*, because the model now depends on the request (tier and reasoning effort).

### 3.15 `api/v1/routes/sql.py`: JSON endpoints + an SSE stream
- `/generate` and `/assist`: release the connection, call the service with `metadata={"user_id": …}` (filter traces per user), then `_respond(...)` saves history and builds the `LLMResponse`.
- **`POST /sql/explain/stream`** is declared with `response_class=EventSourceResponse` and written as an **async generator**:
  - every `yield ServerSentEvent(event="token", data={"text": …})` becomes `event: token` / `data: {"text": "…"}` / blank line on the wire;
  - it ends with exactly one `done` event (the full `LLMResponse`) or one `error` event.
- **Status codes vs streams.** Auth and body validation run *before* streaming starts, so they still produce normal 401/422 JSON. Once the first byte is out, the status (200) is fixed, so later failures, like a rate limit, can only be reported as an `error` event.
- FastAPI enters the SSE producer on the **request-scoped exit stack**, *after* the dependencies, so it unwinds first. The DB session stays open while we stream and save history.
- FastAPI also sends `: ping` keep-alive comments every 15 s and sets `Cache-Control: no-cache` and `X-Accel-Buffering: no`, which stops nginx from buffering the stream.
- If the browser disconnects, the stream task is cancelled and our generator stops consuming the model.

### 3.16 `main.py`
The lifespan calls `configure_logging()` → `configure_tracing(settings)` → `check_database()`. The API version is now 0.2.0.

---

## 4. Frontend, file by file

### 4.1 `lib/api.js`
- **`authFetch(path, {method, body, auth, retry, signal})`**: fetch + `Authorization` header + one silent refresh on 401. It returns the raw `Response`, so both JSON calls and streams build on it. An `AbortError` is re-thrown untouched: the caller cancelled on purpose.
- **`toApiError(res)`** builds an `ApiError` from the envelope and adds `retryAfter` from the `Retry-After` header or `details.retry_after`.
- **`request()`** = `authFetch` + JSON + `toApiError`, the same contract as Phase 0.
- **SSE reader.**
  - **Why not `EventSource`?** The browser's `EventSource` can only send **GET** requests without custom headers, and we need POST plus a Bearer token.
  - **How it reads.** `streamEvents()` reads `res.body.pipeThrough(new TextDecoderStream())` and **buffers** the text, because network chunks don't line up with events.
  - **Event boundaries.** Each complete event ends with a blank line (`\n\n`). `parseSSEBlock()` reads its `event:` and `data:` lines and skips `:` comments (keep-alive pings).
- **`api.streamExplain(request, {onToken, signal})`** calls `onToken(text)` for every piece. It resolves with the `done` payload, or rejects with an `ApiError` built from an `error` event.
- `generateSql` and `assistSql` accept `reasoningEffort`, sent as `reasoning_effort` (`null` = server default).

### 4.2 `components/ReasoningEffortSelect.jsx`
A four-option segmented control: Auto (null), Fast (low), Balanced (medium), Thorough (high). It uses `role="radiogroup"` and `role="radio"` with `aria-checked` for screen readers, and each option has a tooltip with its trade-off.

### 4.3 `components/LLMResultDetails.jsx`
Renders an `LLMResponse`:
- a **validation badge** ("Valid mysql syntax · SELECT", or the first syntax error, with all errors in a tooltip);
- the explanation;
- assumptions ("check these against your schema");
- **`LLMMetrics`**: model · effort, seconds, tokens (with reasoning), cost, and a fallback warning when relevant.

### 4.4 Pages
- **`queryBuilder.jsx`:** "Thinking" switch, result details under the SQL. It also fixes a **pre-existing crash**: the Examples panel used an `examples` array that was never defined, so clicking **Examples** threw a `ReferenceError` (present since the original commit; found by ESLint's `no-undef`).
- **`sql_assistants.jsx`:**
  - Explain mode streams: `onToken` appends text, and a pulsing cursor shows while text arrives.
  - Debug and optimize show the fixed SQL plus details.
  - Each run creates an `AbortController`. A newer run, or leaving the page (cleanup in `useEffect`), aborts the previous stream.
  - `finally` only clears the busy state if this run is still the latest one.

---

## 5. Flows, traced through the code

**Generate (structured):**
1. `queryBuilder` calls `api.generateSql({question, dialect, reasoningEffort})`.
2. The route resolves `CurrentUser` (JWT → `SELECT user`), then `release_connection` (COMMIT).
3. `run_structured`: prompt (`generate_sql@v2`) → `ChatGroq(120b, effort).with_structured_output(SQLAnswer, json_schema, strict)` inside `with_retry` and `with_fallbacks`.
4. Groq decodes under the schema constraint → JSON → `SQLAnswer`, with `usage_metadata` on the raw message.
5. `extract_sql` → `validate_sql` (sqlglot) → `estimate_cost_usd` → `LLMResult`.
6. `history.record` → INSERT with tokens, cost, prompt version and JSONB details.
7. `LLMResponse` → the UI shows the SQL, badge, assumptions and metrics.

**Explain (streamed):**
1. `api.streamExplain` sends a `POST` with the Bearer token.
2. The route validates and authenticates, then returns `200 text/event-stream`.
3. `stream_explanation` runs `astream()` on gpt-oss-20b at low effort and yields text, which the route forwards as `event: token` events.
4. The browser reads chunks, splits events at blank lines, and appends the text.
5. The final chunk carries usage → `LLMResult` → history saved → `event: done`.

**Rate limit:**
1. The primary raises `RateLimitError` (429). `with_retry` ignores it, since it isn't a transient error.
2. `with_fallbacks` runs the fast tier → answer with `fallback_used=true`.
3. If the fast tier is limited too, the first error propagates → `RateLimitedError(retry_after)` → **HTTP 429** with `Retry-After` (or an SSE `error` event while streaming).

---

## 6. Measured live (your Groq key, 2026-10-07)

| Call | Model · effort | Latency | Tokens in / out (reasoning) | Cost |
|---|---|---|---|---|
| generate, structured (probe) | 120b · medium | 1.25 s | 286 / 298 (113) | – |
| generate (probe) | 120b · low | 1.07 s | 238 / 264 (32) | – |
| generate (probe) | 120b · high | 2.33 s | 286 / 844 (661) | – |
| generate (end-to-end via API) | 120b · low | 1.02 s | 356 / 202 (43) | $0.000175 |
| explain stream, before tuning | 20b · medium | first word 1.72 s, done 2.27 s | 173 / 1581 (**1129**) | $0.00049 |
| explain stream, after tuning | 20b · low | first word **0.69 s**, done 1.03 s | 173 / 326 (**6**) | **$0.00011** |

**The optimization story.** Reasoning tokens are generated **before** the first visible word. At medium effort, 71% of the explanation's output was hidden reasoning, so the user stared at an empty box for 1.7 s and we paid for it. Explaining a query doesn't need deep thought, so `explain_sql` now defaults to **low** effort: 2.5× faster to the first word and 4.4× cheaper. Generation keeps medium, because correctness benefits from reasoning. This was decided from measurements rather than intuition, which is the habit Phase 5 (evaluation) formalizes.

At these list prices, 1,000 generated queries cost about **$0.17–0.20**. On Groq's free tier you pay nothing but are rate-limited, which is exactly why the fallback exists.

---

## 7. Problems found and fixed in this phase

| Problem | How we found it | Fix |
|---|---|---|
| Groq SDK silently retried 429s, sleeping up to 60 s each time | reading the SDK source (`_calculate_retry_timeout`) | `max_retries=0`; our own `with_retry` (transient only) + `with_fallbacks` (429) |
| DB connection held for the whole LLM call | reasoning about pool size under concurrency | `release_connection()` before LLM work |
| Explanations slow to start and costly | live measurement (1,129 reasoning tokens) | per-prompt default effort: explain → low |
| "Examples" button crashed the Query Builder (since the first commit) | ESLint `no-undef` while editing the page | defined the `examples` list |
| Blank `LANGSMITH_API_KEY=` would enable tracing with an empty key | reviewing `.env` loading | treat empty or whitespace as missing (+ test) |
| A test leaked `LANGSMITH_TRACING=true` into later tests | reviewing pytest's `monkeypatch.delenv` semantics | `configure_tracing(settings, environ)` writes to a dict in tests |

---

## 8. Tests (51)

| File | Covers |
|---|---|
| `test_sql_and_history.py` (16) | structured answer fields, fence stripping, validation result, history columns + JSONB details, invalid SQL flagged (not hidden), unparseable output → 502, effort passthrough + defaults (incl. explain = low), invalid effort → 422, debug/explain paths, persistent outage → 502, history isolation |
| `test_resilience.py` (4) | `Retry-After` parsing; transient error retried on the same model; 429 → fallback without retrying; both tiers limited → 429 + `Retry-After` |
| `test_streaming.py` (3) | SSE event sequence (several `token`s then `done`), content-type, history saved; 401 before streaming; failure → single `error` event |
| `test_llm_units.py` (12) | sqlglot validation cases + dialect mapping; usage parsing (reasoning, cache); cost math with cached tokens; tracing on/off/blank key; the suite never traces |
| Phase 0 files (16) | `test_auth.py` (12), `test_config.py` (3), `test_database_errors.py` (1): unchanged |

The fake provider in `conftest.py` simulates everything the real one does: structured answers with usage, word-by-word streaming with usage on the last chunk, and queued errors (`rate_limit_error()`, `connection_error()` build real `groq` exception objects).

---

## 9. Run it, and turn on tracing

```bash
cd backend
uv sync
uv run alembic upgrade head
uv run pytest -q
```

`alembic upgrade head` applies migration 2; `pytest` should report 51 passed.

To turn on LangSmith tracing:
1. Create a free account at <https://smith.langchain.com>.
2. Go to **Settings → API Keys** and create a key.
3. In `backend/.env`, set `LANGSMITH_TRACING=true` and `LANGSMITH_API_KEY=lsv2_…`.

The server restarts (thanks to `--reload-include .env`) and logs `LangSmith tracing is on: project 'sqlassist-dev'`. Each request then appears as a trace named `generate_sql`, `debug_sql` or `explain_sql`, showing:
- the prompt messages;
- the JSON schema sent;
- the raw reply and parsed object;
- token counts and latency;
- any retries or fallbacks, as child runs.

---

## 10. Interview questions you can now answer

1. **Three ways to get structured output from an LLM?** JSON mode (valid JSON, no schema guarantee) · function/tool calling (schema as a tool definition; the model fills arguments) · schema-constrained decoding (the decoder can only emit schema-valid tokens). We use the last one.
2. **Why does strict mode need every field required and `additionalProperties: false`?** The decoder must know the exact set of keys at every step to constrain generation; optional or unknown keys would make the grammar ambiguous.
3. **Why `include_raw=True`?** The parsed object drops metadata. We need the raw `AIMessage` for token usage and the model that actually answered, and to handle parsing failures instead of crashing.
4. **Retry vs fallback?** Retry the *same* thing when the failure is likely temporary (network, 5xx). Fall back to *something else* when retrying won't help soon (rate limit, outage of one model).
5. **Why exponential backoff with jitter?** Backoff gives the provider time to recover; jitter spreads simultaneous retries so clients don't hit it in synchronized waves (thundering herd).
6. **Why did we disable the SDK's retries?** It honours `Retry-After` up to 60 s per attempt, so with 2 retries a rate-limited call could block about 2 minutes before our fallback could run.
7. **SSE vs WebSockets vs polling?** SSE is one-way server→client over plain HTTP, simple and proxy-friendly, which suits token streams. WebSockets are bidirectional with their own protocol, for chat-like duplex traffic. Polling is repeated requests: simple but wasteful and laggy.
8. **Why not the browser's `EventSource`?** It only does GET without custom headers; we need POST with a body and a Bearer token, so we parse the stream from `fetch` ourselves.
9. **What is time to first token (TTFT), and what affects it?** The delay until the first visible output: network + queueing + prompt processing + **hidden reasoning**. Lower reasoning effort or a smaller model reduces it.
10. **What are reasoning tokens? Who pays?** Tokens a reasoning model generates to "think" before answering. Usually not shown, billed as output tokens, they count toward `max_tokens` and delay the first visible word.
11. **Why `Decimal`/`NUMERIC` for cost instead of float?** Floats are binary approximations (0.1 + 0.2 ≠ 0.3); money needs exact decimal arithmetic.
12. **JSON vs JSONB in PostgreSQL?** JSON stores the text as-is. JSONB stores a parsed binary form: slightly slower to write, much faster to query, and indexable (GIN).
13. **Why release the DB connection before an LLM call?** Pools are small (5 + 10 overflow by default). Idle-but-held connections during slow external calls exhaust the pool under load while the database does nothing.
14. **How and why version prompts?** Give each prompt a name and version, record it with every result and trace, and bump the version when the wording changes. Then quality changes can be attributed and compared (A/B, evals).
15. **Syntax vs semantic SQL validation?** Syntax: does it parse for the dialect (sqlglot)? Semantics: do the tables and columns exist, do the types fit, is it allowed? That needs the schema (Phase 2) and policies (Phase 6).
16. **How do errors work in a stream?** The 200 status is sent with the first byte, so later errors become in-band `error` events. Errors that can happen *before* streaming (auth, validation) are handled first so they keep proper status codes.
17. **How do you test LLM code without calling an LLM?** Dependency injection plus fake models that return scripted structured answers, stream words, and raise real exception types. Model *quality* is measured separately with evals.
18. **How is LangSmith tracing enabled, and what's the gotcha?** Environment variables (`LANGSMITH_TRACING`, `LANGSMITH_API_KEY`). The SDK caches env vars on first read, so they must be set at startup before any LLM call, and `.env` values must be exported because pydantic-settings doesn't do that.
19. **Why route explanations to the small model at low effort?** Task–model fit: describing a query is easy, so the cheaper, faster tier is good enough. We measured 2.5× faster TTFT and 4.4× lower cost.
20. **Prompt injection: what do the `<sql>` tags do, and what don't they do?** They mark user text as data, which makes accidental instruction-following less likely. They are **not** a security boundary; a determined injection can still work, which is why real defenses (classifiers, least privilege, output policies) come in Phase 6.

---

## 11. Known gaps (carried forward)

- The LLM still doesn't see the user's schema, so `assumptions` lists guesses and semantic checks are impossible. **Phase 2** starts fixing that (schema ingestion).
- No automatic self-correction when validation fails (the user sees the error). This becomes the Validator → Generator reflection loop in **Phase 6**.
- Generation isn't streamed (structured output). Partial-JSON streaming is possible but not worth it yet.
- Costs are list-price *estimates*; the free tier is actually $0. Per-user budgets and quotas come in **Phase 8**.
- ESLint still flags `motion` as unused in some pages (missing JSX plugin rule). This is in the UI phase.
- Raw reasoning (`reasoning_content`) is deliberately not shown to users: providers advise against exposing raw chain-of-thought.
