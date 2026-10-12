# SQLAssist: AI-powered SQL Assistant

> Ask questions in plain English, get correct SQL for **your** database.
> A learning-in-public project that grows into a full SaaS with **schema-aware RAG**, a **LangGraph agent team**, **RAG evaluation** and an **MCP server**.

| | |
|---|---|
| **Backend** | FastAPI (async) · SQLAlchemy 2 + asyncpg · Alembic · PostgreSQL |
| **AI** | LangChain + LangGraph · Groq (`openai/gpt-oss-120b`, `gpt-oss-20b`) · Hugging Face embeddings · Qdrant |
| **Frontend** | React 19 · Vite · Tailwind · Framer Motion |
| **Ops** | uv · Docker Compose · GitHub Actions (planned) |
| **Learning notes** | 📓 [SQLAssist Notebook (PDF)](docs/notebook/SQLAssist-Notebook.pdf): hand-drawn explanations of every concept used here |

---

## Project status

| Phase | Scope | Status |
|---|---|---|
| 0 | Foundation: Postgres, auth, LangChain LLM layer, bug fixes | ✅ done |
| 1 | LLM layer: structured output, SQL validation, SSE streaming, tokens & cost, reasoning effort, retries & fallbacks, prompt versions, LangSmith tracing | ✅ done |
| 2 | Schema ingestion: SQL text / `.sql` files / screenshots (vision LLM) → normalized schema, background jobs, grounded prompts, schema-aware validation, table picker | ✅ done |
| 3 | Embeddings + Qdrant: one document per table, LLM descriptions + synonyms, dense (bge-small) + sparse (BM25) vectors, multi-tenant collection, incremental indexing, search playground | ✅ done |
| 4 | Retrieval: BM25, dense, hybrid (RRF), FK-graph expansion, reranking | ⏭️ next |
| 5 | RAG evaluation: golden set, retrieval metrics, execution accuracy, RAGAS, CI gate | planned |
| 6 | Agents (LangGraph): router, retriever, generator, validator, safety, optimizer, explainer, memory, HITL | planned |
| 7 | MCP server (FastMCP) exposing SQLAssist tools to Claude Desktop / Cursor | planned |
| 8 | SaaS & scale: workspaces, rate limits, caching, observability, UI/UX polish | planned |
| 9 | Ship: Dockerfiles, CI/CD, deployment | planned |

The full plan, with decisions and learning goals per phase, is in [docs/ROADMAP.md](docs/ROADMAP.md).
File-by-file explanations of each phase: [Phase 0: foundation](docs/phases/phase-0-foundation.md) · [Phase 1: LLM layer](docs/phases/phase-1-llm-layer.md) · [Phase 2: schema ingestion](docs/phases/phase-2-schema-ingestion.md) · [Phase 3: embeddings + Qdrant](docs/phases/phase-3-embeddings-qdrant.md).

---

## Architecture

### Target system (green = built, dashed = coming)

```mermaid
flowchart TB
    UI["React + Vite SaaS UI"]:::built

    subgraph API["FastAPI · /api/v1"]
        AUTH["auth + JWT"]:::built
        SQLR["sql + history"]:::built
        ING["schemas API<br/>uploads → 202"]:::built
        QRY["query API (agent runs)"]:::planned
    end

    subgraph WORK["Background & agents"]
        JOB["ingestion job (in-process)<br/>parse → normalize → merge"]:::built
        WRK["indexing (same job)<br/>describe → embed → upsert"]:::built
        AG["LangGraph agent team<br/>router · retriever · generator<br/>validator · safety · explainer"]:::planned
        MCP["MCP server (FastMCP)"]:::planned
    end

    PG[("PostgreSQL<br/>users · history · schemas · tables · jobs")]:::built
    QD[("Qdrant<br/>dense + BM25 vectors<br/>one point per table")]:::built
    RD[("Redis<br/>queue · cache · rate limits")]:::planned
    GQ{{"Groq LLMs<br/>gpt-oss-120b / 20b · qwen vision"}}:::built
    HF{{"Hugging Face models (local, ONNX)<br/>bge-small · BM25 · reranker next"}}:::built
    HOST["Claude Desktop / Cursor"]:::planned

    UI -->|REST + streaming| API
    AUTH --> PG
    SQLR --> PG
    SQLR --> GQ
    ING --> JOB
    JOB --> PG
    JOB -->|screenshots| GQ
    JOB --> WRK
    QRY --> AG
    WRK --> HF
    WRK --> QD
    WRK -->|descriptions| GQ
    ING -->|search| QD
    AG --> QD
    AG --> GQ
    AG <--> MCP
    HOST -->|MCP| MCP
    API -.-> RD

    classDef built fill:#d4f4dd,stroke:#2e7d32,color:#1b2740
    classDef planned fill:#fff8e1,stroke:#c96a00,stroke-dasharray:5 5,color:#1b2740
```

### Backend layers

```mermaid
flowchart LR
    R["api/v1/routes<br/>HTTP in/out, status codes, SSE"] --> S["services<br/>business rules"]
    S --> M["models + db<br/>ORM tables, sessions"]
    S --> L["llm<br/>model factory · retry/fallback<br/>prompts · output schemas · usage"]
    S --> T["sql_tools<br/>sqlglot: validation · DDL extraction<br/>schema catalog"]
    S --> G["rag<br/>documents · embeddings (fastembed)<br/>vector_store (Qdrant)"]
    R -.-> C["core<br/>config · security · exceptions<br/>logging · tracing"]
    S -.-> C
    M -.-> C
```

Lower layers never import upper ones. `services/` knows nothing about HTTP, so the same functions will later be called by LangGraph agents (Phase 6) and MCP tools (Phase 7).

### What happens when you click “Generate SQL”

```mermaid
sequenceDiagram
    autonumber
    actor U as User
    participant FE as React · lib/api.js
    participant API as FastAPI /api/v1/sql/generate
    participant DEP as Depends(get_current_user)
    participant SVC as services/sql.py
    participant LLM as Groq · gpt-oss-120b
    participant DB as PostgreSQL

    U->>FE: question + dialect + schema + ticked tables, clicks Generate
    FE->>API: POST {question, dialect, schema_id, tables, reasoning_effort} + Bearer token
    API->>API: Pydantic validates body (422 if invalid)
    API->>DEP: verify JWT signature, expiry, type=access
    DEP->>DB: SELECT user by id
    API->>DB: load own schema (404 if not yours) → table cards within the budget + catalog
    API->>DB: COMMIT (release the connection before the slow LLM call)
    API->>SVC: generate_sql(provider, question, dialect, effort, schema_context)
    SVC->>LLM: generate_sql@v3: rules (system) + schema cards + request, tagged (human)
    Note over SVC,LLM: network error / 5xx → retry with backoff<br/>429 rate limit → fall back to gpt-oss-20b
    LLM-->>SVC: JSON matching SQLAnswer + token usage
    SVC->>SVC: sqlglot: syntax + unknown tables/columns vs catalog · cost = tokens × price
    SVC-->>API: LLMResult(sql, explanation, assumptions, validation, schema_tables, usage, cost)
    API->>DB: INSERT query_history (schema_id, tokens, cost, prompt version, details)
    API-->>FE: 200 LLMResponse
    FE-->>U: SQL + syntax badge + schema check + "grounded in N tables" + metrics
```

### Uploading a schema (Phase 2): 202 + background job + polling

```mermaid
sequenceDiagram
    autonumber
    actor U as User
    participant FE as Database Setup page
    participant API as FastAPI /schemas/{id}/sources
    participant DB as PostgreSQL
    participant JOB as process_source (background)
    participant V as Groq · qwen vision

    U->>FE: paste SQL / drop .sql file / Ctrl+V screenshot
    FE->>API: POST text (JSON) or file (multipart)
    API->>API: owner check (404) · magic bytes (415) · size (413) · decode
    API->>DB: sha256 seen in this schema?
    alt same content already uploaded
        API-->>FE: 200 existing source (nothing reprocessed)
    else new content
        API->>DB: INSERT schema_sources (status = pending)
        API-->>FE: 202 Accepted + source
        API->>JOB: BackgroundTasks runs after the response
        JOB->>JOB: per-schema lock → re-check status → processing
        opt screenshot
            JOB->>V: image (base64 data URL) → CREATE TABLE text
            JOB->>DB: save transcription
        end
        JOB->>JOB: sqlglot extraction in a thread (to_thread)
        JOB->>DB: merge tables/columns/FKs → ready + stats (or failed + message)
        Note over JOB: Phase 3: same job, still under the lock → index_schema (next diagram)
    end
    loop every 1.5 s while pending/processing
        FE->>API: GET /schemas/{id} + /sources
    end
    FE-->>U: tables, keys, FKs, warnings, what the vision model read
```

A failed upload can simply be sent again (the same content is retried). Jobs interrupted by a server restart are marked failed at startup, so the page never polls forever.

### Indexing a schema for search (Phase 3)

```mermaid
sequenceDiagram
    autonumber
    participant JOB as index_schema (background)
    participant DB as PostgreSQL
    participant LLM as Groq · gpt-oss-20b
    participant EMB as fastembed (CPU, ONNX)
    participant QD as Qdrant

    JOB->>DB: load tables + columns + FKs · index_status = indexing
    loop tables whose structure changed (fingerprint), 8 per call
        JOB->>LLM: table cards → TableDescriptions (strict JSON)
        LLM-->>JOB: description + synonyms per table
        JOB->>DB: save (commit per batch)
    end
    JOB->>JOB: one search document per table (names as words, synonyms, References / Referenced by)
    JOB->>EMB: documents whose text changed (fingerprint) → to_thread
    EMB-->>JOB: dense 384-d (bge-small) + sparse (BM25) vectors
    JOB->>QD: upsert points (id = table id, payload = user_id, schema_id, document...)
    JOB->>QD: delete this schema's points whose table is gone
    JOB->>DB: fingerprints + index_status = ready + stats
    Note over JOB,LLM: LLM rate-limited → skip descriptions, still embed (graceful degradation)
```

Re-running costs only what changed: an unchanged schema re-indexes in ~0.24 s with no LLM call. PostgreSQL stays the source of truth; Qdrant is a derived index that `POST /schemas/{id}/index` can always rebuild.

### Searching a schema (Phase 3)

```mermaid
flowchart LR
    Q["question<br/>“how long do deliveries take”"] --> E1["embed query<br/>bge-small (dense) · BM25 (sparse)<br/>~6 ms on CPU"]
    E1 --> S{"Qdrant query_points<br/>filter: user_id AND schema_id"}
    S -->|"using = dense<br/>cosine similarity"| D["shpmt .586 · ord_hdr .534 · cust .497"]
    S -->|"using = bm25<br/>IDF applied by Qdrant"| K["shpmt 2.99 (only match)"]
    D --> J["join back to PostgreSQL<br/>drop deleted tables"]
    K --> J
    J --> R["ranked tables<br/>(Phase 4: fuse with RRF → rerank → prompt)"]
```

One collection holds every user's tables. The tenant filter is applied *inside* the vector search, so another user's tables can never be returned and `limit` counts only allowed points.

### Streaming an explanation (Server-Sent Events)

```mermaid
sequenceDiagram
    participant FE as React (fetch + ReadableStream)
    participant API as FastAPI /sql/explain/stream
    participant LLM as Groq · gpt-oss-20b

    FE->>API: POST {sql, dialect} + Bearer token
    API->>API: auth + validation first (401/422 are normal JSON errors)
    API-->>FE: 200 Content-Type: text/event-stream
    API->>LLM: chain.astream() at low reasoning effort
    loop every chunk
        LLM-->>API: tokens
        API-->>FE: event: token / data: {"text": "..."}
        FE->>FE: append text to the output panel
    end
    API->>API: save history (tokens, cost)
    API-->>FE: event: done / data: LLMResponse
    Note over FE,API: failures after the 200 → event: error<br/>idle stream → ": ping" keep-alive every 15 s
```

### Authentication: access + refresh tokens

```mermaid
sequenceDiagram
    participant B as Browser (lib/api.js)
    participant A as FastAPI
    participant P as PostgreSQL

    B->>A: POST /auth/login {email, password}
    A->>P: SELECT user WHERE email = …
    A->>A: bcrypt.checkpw (dummy hash if user missing → same timing)
    A-->>B: {access_token (15 min), refresh_token (7 days)}
    B->>A: GET /history (Bearer access)
    A-->>B: 200
    Note over B,A: … access token expires …
    B->>A: GET /history (Bearer expired)
    A-->>B: 401 not_authenticated
    B->>A: POST /auth/refresh {refresh_token}
    alt refresh valid
        A-->>B: 200 new token pair
        B->>A: retry GET /history → 200
    else refresh expired / invalid
        A-->>B: 401 → client clears tokens, redirects to /login
    end
```

Concurrent 401s share **one** refresh request (single-flight), see `frontend/src/lib/api.js`.

### Data model

```mermaid
erDiagram
    USERS ||--o{ QUERY_HISTORY : "has (ON DELETE CASCADE)"
    USERS ||--o{ DB_SCHEMAS : "owns (CASCADE)"
    DB_SCHEMAS ||--o{ SCHEMA_SOURCES : "uploads = job records"
    DB_SCHEMAS ||--o{ SCHEMA_TABLES : "contains"
    SCHEMA_TABLES ||--o{ SCHEMA_COLUMNS : "has"
    SCHEMA_TABLES ||--o{ SCHEMA_RELATIONSHIPS : "foreign keys out"
    DB_SCHEMAS |o--o{ QUERY_HISTORY : "grounded (SET NULL)"
    USERS {
        uuid id PK
        varchar email UK "normalized lowercase"
        varchar name
        varchar hashed_password "bcrypt"
        boolean is_active
        timestamptz created_at
        timestamptz updated_at
    }
    QUERY_HISTORY {
        uuid id PK
        uuid user_id FK "indexed with created_at"
        varchar tool "generate | debug | explain | optimize"
        varchar dialect
        text input_text
        text output_text
        varchar model "the model that actually answered"
        int latency_ms
        timestamptz created_at
        varchar prompt_version "e.g. generate_sql@v2"
        varchar reasoning_effort "low | medium | high"
        int input_tokens
        int output_tokens "includes reasoning"
        int reasoning_tokens
        numeric cost_usd "12,8 exact decimal"
        jsonb details "explanation, assumptions, tables, validation, schema tables"
        uuid schema_id FK "nullable"
    }
    DB_SCHEMAS {
        uuid id PK
        uuid user_id FK
        varchar name "unique per user"
        varchar dialect
        text description
        varchar index_status "none | pending | indexing | ready | failed"
        text index_error
        jsonb index_stats "embedded, unchanged, enriched, cost, seconds"
        timestamptz indexed_at
    }
    SCHEMA_SOURCES {
        uuid id PK
        uuid schema_id FK
        varchar kind "sql_text | sql_file | image"
        varchar content_hash "sha256, unique per schema"
        text text "SQL or vision transcription"
        bytea raw "image bytes"
        varchar status "pending | processing | ready | failed"
        text error
        jsonb warnings
        jsonb stats
    }
    SCHEMA_TABLES {
        uuid id PK
        uuid schema_id FK
        uuid source_id FK "last upload that described it"
        varchar key "normalized, unique per schema"
        varchar db_schema
        varchar name
        text comment
        boolean inferred "seen only in queries"
        text description "LLM-written, for search"
        jsonb synonyms "LLM-written, for search"
        varchar enrichment_hash "fingerprint of what was described"
        varchar index_hash "fingerprint of what was embedded"
        timestamptz indexed_at
    }
    SCHEMA_COLUMNS {
        uuid id PK
        uuid table_id FK
        varchar name "unique per table"
        varchar data_type
        boolean nullable
        boolean is_primary_key
        boolean is_unique
        text default
        text comment
        int position
    }
    SCHEMA_RELATIONSHIPS {
        uuid id PK
        uuid from_table_id FK
        jsonb from_columns
        varchar to_table_key "resolved when read"
        jsonb to_columns
        boolean inferred "guessed from a join"
    }
```

A relationship points at its target by **key**, not by a database foreign key: uploads arrive in any order, so `order_items → products` can be stored before `products` exists.

### LLM resilience policy

```mermaid
flowchart LR
    REQ["LLM call"] --> P["primary tier<br/>(gpt-oss-120b)"]
    P -->|ok| OK["answer"]
    P -->|"network error / 5xx"| RT["retry same model<br/>exp. backoff + jitter<br/>max 2 retries"]
    RT --> P
    P -->|"429 rate limit"| F["fallback tier<br/>(gpt-oss-20b)"]
    F -->|ok| OK2["answer<br/>fallback_used = true"]
    F -->|"429 again"| E["HTTP 429 + Retry-After"]
```

The Groq SDK's own retries are switched off (`max_retries=0`). By default it would sleep for the server's `Retry-After`, up to 60 s on every attempt, before our fallback could react.

### The RAG pipeline (ingestion + indexing built in Phases 2–3; retrieval in Phase 4)

```mermaid
flowchart LR
    subgraph Ingestion["Ingestion (offline, background job)"]
        IN["SQL text / .sql file / screenshot"]:::built --> PA["parse<br/>sqlglot + vision LLM"]:::built
        PA --> NO["normalize + merge<br/>tables, columns, PK/FK"]:::built
        NO --> CH["chunk<br/>1 table = 1 card"]:::built
        CH --> EN["describe<br/>LLM synonyms"]:::built
        EN --> EM["embed<br/>bge-small + BM25"]:::built
        EM --> QD[("Qdrant")]:::built
    end
    subgraph Query["Query (online)"]
        Q["question + chosen tables"]:::built --> RW["rewrite"]:::planned
        RW --> HY["hybrid search<br/>BM25 + dense"]:::planned
        HY --> RRF["RRF fusion"]
        RRF --> FK["FK-graph expand"]
        FK --> RR["rerank"]
        RR --> PR["prompt"]
        PR --> G["LLM"]
        G --> V{"validate<br/>sqlglot"}
        V -->|errors| G
        V -->|ok| OUT["SQL ✓"]
    end
    QD -.-> HY

    classDef built fill:#d4f4dd,stroke:#2e7d32,color:#1b2740
    classDef planned fill:#fff8e1,stroke:#c96a00,stroke-dasharray:5 5,color:#1b2740
```

Today the SQL prompt still gets the user's table selection, or every table up to a character budget (`SCHEMA_CONTEXT_MAX_CHARS`). Phase 3 built the index and single-method search (dense or BM25, try them in the Database Setup search playground); Phase 4 fuses them (RRF), expands along foreign keys, reranks and feeds the result to the prompt, measured against the budget baseline in Phase 5.

### Coming next: the agent graph (Phase 6)

```mermaid
flowchart TB
    START((start)) --> RT{"Router / Intent<br/>(fast model)"}
    RT -->|generate| RET["Retriever"]
    RT -->|debug| VAL
    RT -->|optimize| OPT["Optimizer"]
    RT -->|explain| EXP["Explainer"]
    RET --> GEN["SQL Generator<br/>(primary model)"]
    GEN --> VAL["Validator / Critic"]
    VAL -->|errors, ≤ 3 tries| GEN
    OPT --> VAL
    VAL --> SAFE["Safety Guard<br/>read-only policy"]
    SAFE -->|non-SELECT| HITL["Human approval<br/>(interrupt → resume)"]
    SAFE --> ANS((answer))
    HITL --> ANS
    EXP --> ANS
```

---

## Getting started

### Prerequisites
- Python 3.12 via [uv](https://docs.astral.sh/uv/) · Node 20+ · PostgreSQL 15+ (local install **or** Docker)
- A free Groq API key: <https://console.groq.com/keys>

### 1. Database: pick one

**Option A: a local PostgreSQL (managed with pgAdmin).** In pgAdmin, right-click your server → **Query Tool**, then run these statements **one at a time** (select a line, press F5). `CREATE DATABASE` refuses to run together with other statements.

```sql
CREATE ROLE sqlassist WITH LOGIN PASSWORD 'choose-a-strong-password';
```

```sql
CREATE DATABASE sql_assistant OWNER sqlassist;
```

A dedicated role is least privilege: the app owns its own database and nothing else, unlike the `postgres` superuser. For quick local experiments you can skip the role, create only the database, and use `postgres` plus your install password.

**Option B: Docker.**

```bash
docker compose up -d
```

This starts PostgreSQL on port **5433** (user `postgres`, password `postgres`, database `sql_assistant`) and Qdrant on 6333.

### 2. Backend

```bash
cd backend
cp .env.example .env
```

Edit `backend/.env`:

| Variable | Option A (local) | Option B (Docker) |
|---|---|---|
| `POSTGRES_HOST` | `localhost` | `localhost` |
| `POSTGRES_PORT` | `5432` | `5433` |
| `POSTGRES_USER` | `sqlassist` (or `postgres`) | `postgres` |
| `POSTGRES_PASSWORD` | the password from step 1 | `postgres` |
| `POSTGRES_DB` | `sql_assistant` | `sql_assistant` |

Also set `GROQ_API_KEY` and `JWT_SECRET_KEY` (32+ random characters). Special characters in the password need no escaping: the URL is built with SQLAlchemy's `URL.create()`. Hosted platforms that hand you one connection string can set `DATABASE_URL` instead; it takes precedence. Then:

```bash
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --reload-include .env --port 8000
```

**Vector search (Qdrant).** Nothing to install by default: with `QDRANT_URL` empty, Qdrant runs *embedded* in the API process and stores its data in `backend/.qdrant/` (one process at a time). Alternatives: `docker compose up -d qdrant` + `QDRANT_URL=http://localhost:6333`, or a free Qdrant Cloud cluster (`QDRANT_URL` + `QDRANT_API_KEY`). The first index downloads two small Hugging Face models (~80 MB) into `backend/.cache/fastembed/`.

`alembic upgrade head` creates the tables. In pgAdmin you should then see `users`, `query_history`, `db_schemas`, `schema_sources`, `schema_tables`, `schema_columns`, `schema_relationships` and `alembic_version` under **sql_assistant → Schemas → public → Tables** (refresh the tree first).

On startup the API logs `Database ready: postgresql+asyncpg://…` or explains what's wrong. You can also check <http://localhost:8000/api/v1/health/ready> (`"database": "up"`, `"vector_store": "up"`). Settings are read once at startup; `--reload-include .env` makes the dev server restart when you edit `.env`, not only when `.py` files change.

Interactive API docs: <http://localhost:8000/docs>

### Optional: LangSmith tracing

To inspect every LLM call (prompt, answer, tokens, latency, retries and fallbacks):
1. Create a free account at <https://smith.langchain.com>.
2. Go to **Settings → API Keys** and create a key.
3. In `backend/.env`, set `LANGSMITH_TRACING=true` and `LANGSMITH_API_KEY=<your key>`.

The dev server restarts by itself and logs `LangSmith tracing is on: project 'sqlassist-dev'`. Each run is tagged with its prompt version and reasoning effort, and carries the user id as metadata. While tracing is on, prompts and answers are stored in LangSmith's cloud.

### Troubleshooting the database connection

| Message (server log or API error) | Cause | Fix |
|---|---|---|
| `password authentication failed for user "…"` | wrong `POSTGRES_USER` / `POSTGRES_PASSWORD`, or the server still runs with an older `.env` | fix `backend/.env`, then restart the API |
| `database "sql_assistant" does not exist` | database not created yet | step 1 above (pgAdmin Query Tool or Docker) |
| `connected …, but it has no tables yet` / `relation "users" does not exist` | migrations not applied | `uv run alembic upgrade head` |
| `Connect call failed` / connection refused | PostgreSQL not running, or wrong host/port | start the PostgreSQL service (Windows: Services → postgresql-x64-17) or check `POSTGRES_PORT` |
| API returns `503 database_unavailable` | any of the above | read the API's startup log line for the exact reason |

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>. To run both apps together from the repo root, use `npm install` then `npm run dev`.

### Tests & checks

```bash
cd backend
uv run pytest
uv run ruff check app tests
```

Tests use in-memory SQLite, a fake LLM provider (which can simulate structured answers, streaming, a vision model, table descriptions, rate limits and outages), a deterministic fake embedder and a real Qdrant running in memory, so they need no database, network, model download or API key. Background ingestion jobs run against the same in-memory database.

---

## API (v1)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/api/v1/health/live` · `/health/ready` | – | liveness · readiness (DB check + vector store up/down) |
| POST | `/api/v1/auth/signup` | – | create account → `201` |
| POST | `/api/v1/auth/login` | – | email + password → token pair |
| POST | `/api/v1/auth/refresh` | refresh token | new token pair |
| GET / PATCH / DELETE | `/api/v1/users/me` | ✓ | read / rename / delete own account |
| POST | `/api/v1/users/me/password` | ✓ | change password |
| POST | `/api/v1/sql/generate` | ✓ | natural language → validated SQL (structured output) |
| POST | `/api/v1/sql/assist` | ✓ | `mode`: `debug` · `optimize` (structured) · `explain` (text) |
| POST | `/api/v1/sql/explain/stream` | ✓ | explanation streamed as Server-Sent Events: `token`… then `done` or `error` |
| GET | `/api/v1/history?limit&offset` | ✓ | own history, newest first, with tokens, cost and details |
| DELETE | `/api/v1/history/{id}` | ✓ | delete own entry (`404` if not yours) |
| GET / POST | `/api/v1/schemas` | ✓ | list own schemas (status, counts) · create one (`409` on a duplicate name) |
| GET / PATCH / DELETE | `/api/v1/schemas/{id}` | ✓ | tables with columns and FKs · rename / change dialect · delete everything |
| DELETE | `/api/v1/schemas/{id}/tables/{table_id}` | ✓ | remove one table |
| POST | `/api/v1/schemas/{id}/sources/text` | ✓ | `{"sql": "…"}` → `202` + source (`200` if this exact content was already uploaded) |
| POST | `/api/v1/schemas/{id}/sources/file` | ✓ | multipart `file`: `.sql`/`.ddl`/`.txt` or PNG/JPEG/WebP → `202` (`413` too large, `415` other types) |
| GET | `/api/v1/schemas/{id}/sources` · `/sources/{source_id}` | ✓ | uploads, newest first · poll one until `ready` or `failed` |
| POST | `/api/v1/schemas/{id}/index` | ✓ | rebuild the search index → `202`; poll the schema's `index_status` (unchanged tables are skipped) |
| GET | `/api/v1/schemas/{id}/search?q=&mode=dense\|sparse&limit=5` | ✓ | tables most related to `q`, by meaning (dense) or keywords (BM25), with scores and the indexed text |

All three SQL endpoints accept an optional `reasoning_effort` (`low` · `medium` · `high`), and an optional `schema_id` plus `tables` (names to focus on; omitted = the whole schema up to the prompt budget). Every answer (`LLMResponse`) contains:
- `output`, `explanation`, `assumptions`, `tables_used`;
- `validation` (`valid`, `dialect`, `statement_types`, `errors`, plus `schema_checked` and `schema_issues` such as `Unknown column: o.order_date`);
- `schema_id`, `schema_tables` (what the model was shown), `schema_truncated`;
- `model`, `prompt_version`, `reasoning_effort`, `latency_ms`;
- `usage` (input, output, reasoning and cached tokens), `cost_usd`, `fallback_used`, `history_id`.

Every error uses one envelope with a matching HTTP status. A `429 rate_limited` also carries a `Retry-After` header.

```json
{ "error": { "code": "validation_error", "message": "Request validation failed.", "details": [ { "field": "password", "message": "..." } ] } }
```

---

## Repository layout

```
backend/
  app/
    main.py               app factory: CORS, error handlers, routers, lifespan (tracing, DB check)
    core/                 config (pydantic-settings), security (bcrypt, JWT), exceptions, logging,
                          tracing (LangSmith)
    db/                   declarative Base + mixins, async engine/session, release_connection
    models/               User, QueryHistory, DbSchema, SchemaSource, SchemaTable, SchemaColumn,
                          SchemaRelationship (SQLAlchemy 2 typed ORM)
    schemas/              Pydantic request/response models (API contracts)
    services/             auth, sql (structured + streamed LLM calls), history,
                          schemas (CRUD, uploads, merge rules, prompt context), ingestion (background job),
                          indexing (enrich → embed → Qdrant, search), jobs (job deps + per-schema locks)
    rag/                  documents (search text per table), embeddings (fastembed: bge-small + BM25),
                          vector_store (Qdrant: collection, tenant-filtered search, deletes)
    llm/                  client (ChatGroq tiers, retry/fallback, vision model), prompts (versioned,
                          schema slots), vision (screenshot → DDL), enrichment (table descriptions),
                          output_schemas, usage (tokens, cost)
    sql_tools/            sqlglot: validation (syntax + unknown tables/columns), ddl (schema
                          extraction), catalog (name normalization)
    api/deps.py           shared dependencies: DbSession, SessionFactory, CurrentUser, LLM, Embeddings,
                          VectorIndex, Jobs
    api/v1/routes/        auth, users, sql (incl. SSE stream), history, schemas, health
  alembic/                migrations (env.py uses the app's DB settings)
  tests/                  pytest: SQLite in-memory, fake LLM + fake embedder, in-memory Qdrant (no network)
  pyproject.toml, uv.lock, requirements.txt (exported for pip users)
frontend/
  src/lib/api.js          the only module that talks to the backend (tokens, refresh, errors, SSE, uploads)
  src/lib/                dialects (one list for every dropdown), format helpers
  src/components/         ProtectedRoute, ReasoningEffortSelect, LLMResultDetails, SchemaSearch (index + playground)
  src/*.jsx               pages (DatabaseSetup = schema workspace, queryBuilder = table picker + generate)
docs/
  ROADMAP.md              phases, decisions, learning goals
  phases/                 per-phase deep dives (what changed, why, how it works)
  notebook/               hand-drawn study notebook (HTML source → PDF via build.mjs)
docker-compose.yml        PostgreSQL + Qdrant for local development
```

## The learning notebook

[`docs/notebook/SQLAssist-Notebook.pdf`](docs/notebook/SQLAssist-Notebook.pdf) is a hand-written-style, diagram-first explanation of every concept in this project: HTTP, async, ORMs, JWT, LLMs, LangChain, RAG, embeddings, Qdrant/HNSW, BM25/hybrid/RRF, reranking, RAG evaluation metrics, agents, LangGraph, memory, human-in-the-loop, MCP, guardrails, Docker and scaling. It grows with every phase. To rebuild it (needs Chrome or Edge and internet for fonts):

```bash
node docs/notebook/build.mjs
```

Add `--check` to find pages that overflow, or `--png 3,12` to preview single pages.
