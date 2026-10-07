# Phase 0: Foundation (deep dive)

> **Goal:** turn the prototype into a correct, secure, testable base that the AI features (RAG, agents, MCP) can be built on.
> **Status:** done on 2026-10-07 · 23 tests passing · verified live against Groq and end-to-end in the browser.
> Pair this with the notebook chapters 2–5 ([PDF](../notebook/SQLAssist-Notebook.pdf)) for the concepts behind each piece.

---

## 0. TL;DR: what changed

| Area | Before | After |
|---|---|---|
| Database | MongoDB (Motor), history never actually saved | **PostgreSQL** with SQLAlchemy 2 async ORM + **Alembic** migrations |
| Passwords | stored and compared in **plain text** | **bcrypt** hashes (salted, cost 12) |
| Auth | JWT created but **never verified**; every route public | access + refresh JWTs, `Depends(get_current_user)` on every private route |
| User data | `GET /user-data/{user_id}`: anyone could read anyone (IDOR) | `GET /users/me`: identity comes from the token |
| LLM | sync Groq SDK, **deprecated model** (all calls failed), prompts as f-strings | **LangChain** LCEL chains, async, `gpt-oss-120b/20b` from config, prompt templates |
| Errors | HTTP 200 with `{"error": ...}` | real status codes + one JSON error envelope |
| Structure | 6 route files doing everything | layers: `core / db / models / schemas / services / llm / api` |
| Dependencies | empty `requirements.txt` | `pyproject.toml` + `uv.lock` (+ exported `requirements.txt`) |
| Tests | none | 23 pytest tests (SQLite in memory + fake LLM) |
| Frontend | 5 hard-coded `fetch("http://localhost:8000/...")`, no route guards | one API client (`lib/api.js`) with token refresh; `ProtectedRoute` |

---

## 1. Backend folder map

```
backend/
├── pyproject.toml        project metadata + dependencies (read by uv)
├── uv.lock               exact pinned versions of every package (reproducible installs)
├── requirements.txt      exported from uv.lock for people who use plain pip
├── .python-version       "3.12": uv creates the venv with this interpreter
├── .env / .env.example   secrets & settings (real .env is git-ignored)
├── alembic.ini           Alembic configuration (logging, script location)
├── alembic/
│   ├── env.py            how Alembic connects (uses our settings + our models)
│   └── versions/         one file per schema change ("migration")
├── app/
│   ├── main.py           creates the FastAPI app (entrypoint for uvicorn)
│   ├── core/             cross-cutting: config, security, exceptions, logging
│   ├── db/               SQLAlchemy Base class, engine, sessions
│   ├── models/           ORM classes = database tables
│   ├── schemas/          Pydantic classes = API request/response shapes
│   ├── llm/              LangChain model factory, prompt templates, output parsers
│   ├── services/         business logic (no HTTP knowledge)
│   └── api/
│       ├── deps.py       shared dependencies (DB session, current user, LLM)
│       └── v1/           version 1 of the HTTP API
│           ├── router.py
│           └── routes/   auth.py, users.py, sql.py, history.py, health.py
└── tests/                pytest suite
```

**Why this split?** Each folder answers one question:

- `schemas/`: “what does the API accept and return?”
- `models/`: “what is stored?”
- `services/`: “what are the rules?”
- `api/`: “how is it exposed over HTTP?”

The **dependency rule** is that imports only go downward (`api → services → models/db`, everyone may use `core`). That's what lets Phase 6 agents and Phase 7 MCP tools call `services/` directly without dragging HTTP along.

> ⚠️ The old files `app/auth.py`, `app/database/`, `app/routes/` and the committed `__pycache__/` folders are **no longer imported anywhere** and should be deleted (see §9).

---

## 2. Libraries and why we chose them

| Library | What it is | Why we use it | Alternatives |
|---|---|---|---|
| **FastAPI** | async web framework built on Starlette + Pydantic | type-hint driven validation, dependency injection, auto OpenAPI docs, async-first | Flask (sync), Django (heavier) |
| **Uvicorn** | ASGI server | runs the FastAPI app; `--reload` for dev | Hypercorn, Gunicorn+uvicorn workers (prod) |
| **Pydantic v2 / pydantic-settings** | validation via type hints / env-var settings | validates requests *and* config at startup (fail fast on missing keys) | marshmallow, python-dotenv only |
| **email-validator** | RFC-compliant email checks | required by Pydantic's `EmailStr` | regex (fragile) |
| **SQLAlchemy 2 (async)** | ORM + SQL toolkit | typed models (`Mapped[...]`), unit-of-work sessions, works with Alembic | Tortoise, SQLModel (built on SQLAlchemy) |
| **asyncpg** | async PostgreSQL driver | fastest Postgres driver for asyncio | psycopg 3 async |
| **Alembic** | migration tool | versioned, reversible schema changes; autogenerate from models | hand-written SQL scripts |
| **bcrypt** | password hashing | slow, salted, industry standard | argon2 (also great), passlib (unmaintained) |
| **PyJWT** | JSON Web Tokens | maintained, simple API | python-jose (the old code; unmaintained) |
| **langchain-core / langchain-groq** | LLM abstractions + Groq integration | prompts, chat models, parsers, tool calling, and LangGraph builds on it | raw Groq SDK |
| **pytest / pytest-asyncio / httpx / aiosqlite** | testing | async tests, in-process HTTP client, in-memory DB | unittest |
| **ruff** | linter + formatter | one fast tool replacing flake8/isort/black | flake8 + black |
| **uv** | package/venv manager | lockfile, fast installs, manages Python versions | pip + venv, poetry |

---

## 3. Backend file-by-file

### 3.1 `pyproject.toml`
- `[project].dependencies`: runtime packages. `[dependency-groups].dev`: test/lint tools that never ship.
- `requires-python = ">=3.12,<3.13"`: ML libraries (torch, sentence-transformers in Phase 3) support 3.12 well.
- `[tool.uv] package = false`: this is an app, not a library to publish.
- `[tool.pytest.ini_options]`: `asyncio_mode = "auto"` lets plain `async def test_...` functions run without decorators.
- `[tool.ruff]`: lint rules (`E/F` errors, `I` import order, `UP` modern syntax, `B` bugbear, `ASYNC` async pitfalls).

Commands: `uv sync` (create `.venv`, install from `uv.lock`), `uv run <cmd>` (run inside the venv).

### 3.2 `app/core/config.py`: settings
**Imports:** `BaseSettings, SettingsConfigDict` from **pydantic-settings**; `Field, SecretStr` from **pydantic**; `URL` from `sqlalchemy.engine`; `lru_cache` from the standard library.

- `class Settings(BaseSettings)`: every attribute maps to an env var of the same name (case-insensitive): `postgres_password` ← `POSTGRES_PASSWORD`. Values come from real environment variables first, then the `.env` file.
- `SecretStr`: wraps secrets so `print(settings)` shows `**********`. Read them with `.get_secret_value()`.
- `jwt_secret_key: SecretStr = Field(min_length=32)`: startup **fails** if the secret is too short. Our old 13-character secret is exactly what this catches.
- `cors_origins: list[str]`: lists are parsed from JSON in env vars (`CORS_ORIGINS=["http://..."]`).
- **Database settings** come as five fields: `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD` and `POSTGRES_DB`. These are the same login you use in pgAdmin.
  - The `sqlalchemy_url` property assembles them with `URL.create(drivername="postgresql+asyncpg", ...)`. The password stays a separate component, so characters like `@ : / # %` need no URL-encoding. In a hand-written URL, `p@ss` would make everything after the `@` look like the host.
  - The URL object's `repr()` masks the password, so it's safe to log.
  - If `DATABASE_URL` is set (cloud hosts give you one string; our tests use SQLite), it takes precedence over the five fields. `tests/test_config.py` covers both paths and the special-character round trip.
- `get_settings()` is wrapped in `@lru_cache`, so `.env` is parsed once. `settings = get_settings()` is the module-level instance everyone imports.

**Used by:** nearly everything (`security.py`, `session.py`, `client.py`, `main.py`, `alembic/env.py`).

### 3.3 `app/core/security.py`: bcrypt + JWT
**Imports:** `bcrypt`, `jwt` (PyJWT), `uuid`, `datetime`; `settings` from `app.core.config`.

- `hash_password(pw)`: `bcrypt.hashpw(pw.encode(), bcrypt.gensalt())`. `gensalt()` makes a random 16-byte salt with cost 12; the result is a 60-char string that embeds algorithm, cost, salt and hash.
- `verify_password(pw, hashed)`: `bcrypt.checkpw` re-hashes with the embedded salt and compares in constant time. If `hashed is None` (unknown email) we still run a check against `_DUMMY_HASH`, so “no such user” takes as long as “wrong password” (**prevents user enumeration by timing**).
- `BCRYPT_MAX_BYTES = 72`: bcrypt only uses the first 72 bytes (bcrypt ≥ 5 raises an error beyond that). The schema rejects longer passwords.
- `create_token(subject, token_type)`: builds claims `sub` (user id), `type` (`access`/`refresh`), `iat`, `exp`, `jti` (random id) and signs them with HS256 + the secret.
- `decode_token(token, expected_type)`: `jwt.decode(..., algorithms=[settings.jwt_algorithm], options={"require": [...]})` verifies the signature and expiry, requires the claims, then checks `type`. Pinning `algorithms` blocks the `alg: none` attack. Any problem raises `jwt.InvalidTokenError`.

**Used by:** `services/auth.py`, `api/deps.py`, `schemas/auth.py` (the 72-byte constant).

### 3.4 `app/core/exceptions.py`: errors → HTTP
**Imports:** `FastAPI, Request` from fastapi; `RequestValidationError` from `fastapi.exceptions`; `JSONResponse`; Starlette's `HTTPException`.

- `AppError` is the base class with `status_code`, `code`, `message`, `details`. Subclasses: `BadRequestError` 400, `AuthenticationError` 401, `PermissionDeniedError` 403, `NotFoundError` 404, `ConflictError` 409, `LLMServiceError` 502, `DatabaseUnavailableError` 503.
- `register_exception_handlers(app)` installs 4 handlers:
  1. `AppError` → its status + envelope (adds `WWW-Authenticate: Bearer` on 401, per the HTTP spec).
  2. `RequestValidationError` (Pydantic) → 422 with `details: [{field, message}]`.
  3. Starlette `HTTPException` (e.g. unknown route 404) → same envelope.
  4. any other `Exception` → generic 500 (never leaks internals), logged as a **one-line** summary.
     - A handler registered for plain `Exception` runs inside Starlette's `ServerErrorMiddleware`, which **re-raises the exception after sending the response**, so the server (uvicorn) can log it.
     - That means uvicorn already prints the full traceback; logging it ourselves too was why tracebacks appeared twice.

**Why:** services raise *domain* errors (`ConflictError`) and stay HTTP-agnostic. The translation happens in one place.

### 3.5 `app/core/logging.py`
`configure_logging()` sets the format and level (from `LOG_LEVEL`) and quiets `httpx` (which logs every Groq call). It's called once in the app lifespan.

### 3.6 `app/db/base.py`: ORM foundations
**Imports:** `DeclarativeBase, Mapped, mapped_column` from `sqlalchemy.orm`; `DateTime, MetaData, func` from `sqlalchemy`.

- `Base(DeclarativeBase)`: every model inherits from it; `Base.metadata` is the registry of all tables (used by Alembic and tests).
- `NAMING_CONVENTION`: deterministic constraint names (`pk_users`, `uq_users_email`, `fk_query_history_user_id_users`). Alembic needs names to drop or alter constraints later.
- `UUIDPrimaryKeyMixin`: `id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)`. SQLAlchemy maps `uuid.UUID` to Postgres' native `UUID` type.
- `TimestampMixin`: `created_at` / `updated_at` with a **Python-side** `default=utcnow` (the value exists on the object immediately, with no DB round trip needed in async code) **and** a `server_default=func.now()` (rows inserted by raw SQL still get a value). `onupdate=utcnow` refreshes `updated_at` on every ORM update.

### 3.7 `app/db/session.py`: engine and sessions
**Imports:** `create_async_engine, async_sessionmaker, AsyncSession` from `sqlalchemy.ext.asyncio`; `inspect` from `sqlalchemy`; `make_url` from `sqlalchemy.engine`; `DBAPIError` from `sqlalchemy.exc`; `settings`; `DatabaseUnavailableError`.

- `engine = create_async_engine(settings.sqlalchemy_url, pool_pre_ping=True)` is created once per process and owns a **connection pool**. The driver name `postgresql+asyncpg` selects the PostgreSQL dialect and the asyncpg driver.
- `SessionLocal = async_sessionmaker(engine, expire_on_commit=False)` is a session factory. `expire_on_commit=False` keeps loaded attributes readable after `commit()`. Otherwise reading `user.email` after commit would try a lazy reload, which async SQLAlchemy forbids (`MissingGreenlet`).
- `get_db()` is an **async generator dependency**: it opens a session, `yield`s it to the route, and the `async with` block closes it (returning the connection to the pool) after the response, even on errors.
  - Before yielding, it calls `await session.connection()` to borrow a pooled connection **up front**.
  - If PostgreSQL can't be reached or rejects the login (`DBAPIError`, or an `OSError` such as connection refused or a timeout), it logs one line, e.g. `Database connection failed (postgresql+asyncpg://postgres:***@localhost:5432/sql_assistant): password authentication failed for user "postgres"`.
  - It then raises `DatabaseUnavailableError` → **503** `database_unavailable`, instead of a 500 with a long traceback from deep inside the first query.
- `check_database()` runs once at startup (from the lifespan in `main.py`). It connects and uses SQLAlchemy's `inspect(...).has_table("alembic_version")` to check that migrations were applied. It logs one of:
  - `Database ready: …`
  - `…has no tables yet. Run: uv run alembic upgrade head`
  - `Cannot connect … Check the POSTGRES_* values in backend/.env`

  It never stops the app, so `/docs` and `/health` keep working while you fix the config.
- **Settings are read once per process.** Editing `.env` doesn't affect a running server until it restarts. Plain `--reload` only watches `*.py` files, so the dev command adds `--reload-include .env`. (Lesson learned the hard way: the server kept using an old placeholder password after `.env` was fixed.)

### 3.8 `app/models/`: tables
- `user.py`, `class User(UUIDPrimaryKeyMixin, TimestampMixin, Base)`: `email` (unique + indexed), `name`, `hashed_password`, `is_active`, and `queries` relationship (`cascade="all, delete-orphan", passive_deletes=True`). `passive_deletes` lets PostgreSQL's `ON DELETE CASCADE` delete the children instead of SQLAlchemy loading them first.
- `query_history.py`, `class QueryHistory`: `user_id` FK with `ondelete="CASCADE"`, `tool`, `dialect`, `input_text`, `output_text`, `model`, `latency_ms`, `created_at`. A composite index `(user_id, created_at)` serves “my history, newest first”.
- `__init__.py` imports both classes. **Importing a model is what registers its table** on `Base.metadata`, which `alembic/env.py` and the tests rely on.
- `TYPE_CHECKING` imports avoid circular imports at runtime while keeping type hints for editors.

### 3.9 `app/schemas/`: the API contract (Pydantic)
- `auth.py`:
  - `Password = Annotated[str, Field(min_length=8), AfterValidator(_check_password_bytes)]` is a reusable type that enforces 8+ characters and ≤ 72 bytes.
  - `NormalizedEmail` is `EmailStr` + trimming + lowercasing, so `Ada@X.com` and `ada@x.com` are the same account.
  - `SignupRequest`, `LoginRequest`, `RefreshRequest`, `TokenPair`.
- `user.py`:
  - `UserRead(model_config = ConfigDict(from_attributes=True))` can be built directly from a SQLAlchemy `User`. It has **no password field**, so a hash can never leak in a response.
  - `UserUpdate` (name only) and `PasswordChange`.
- `sql.py`:
  - `AssistMode = Literal["debug", "explain", "optimize"]`: any other value → 422 automatically.
  - `MAX_INPUT_CHARS = 20_000` protects the context window and our token budget.
  - `GenerateSQLRequest`, `AssistSQLRequest`, `LLMResponse`, and `QueryHistoryRead` / `QueryHistoryPage` (pagination: `items`, `total`, `limit`, `offset`).

### 3.10 `app/llm/`: the LangChain layer
- `client.py`:
  - **Imports:** `ChatGroq` from `langchain_groq`; `BaseChatModel` from `langchain_core.language_models`.
  - `get_chat_model(tier)` returns a cached `ChatGroq(model=..., api_key=..., temperature=0.1, timeout=60, max_retries=2)`. There are two tiers: `primary` (gpt-oss-120b) and `fast` (gpt-oss-20b).
  - `get_primary_llm()` is the FastAPI dependency. Typing everything as `BaseChatModel` (the abstract interface) means a fake model or another provider can be swapped in.
  - `model_name(llm)` reads the model id for history records.
- `prompts.py`:
  - **Imports:** `ChatPromptTemplate` from `langchain_core.prompts`.
  - One template per task (`GENERATE_SQL_PROMPT`, `DEBUG_…`, `OPTIMIZE_…`, `EXPLAIN_…`) built from `(role, text)` pairs; `{dialect}`, `{question}` and `{sql}` are placeholders filled at run time.
  - Shared `SQL_ONLY_RULES` and an “assumptions go in `--` comments” escape hatch. **Explain** has its own markdown-prose prompt; the old code contradicted itself here.
- `parsers.py`: `extract_sql(text)` uses a regex to unwrap ```` ```sql … ``` ```` fences that models add despite instructions.

### 3.11 `app/services/`: business logic
- `auth.py`:
  - `register_user`: check the email is unused → `ConflictError`; hash the password; `db.add` + `commit`. It also catches `IntegrityError` for the race where two signups for the same email arrive at once (the unique index wins and we return 409).
  - `authenticate`: one identical error for unknown email / wrong password / inactive account.
  - `issue_tokens(user)` returns a `TokenPair`.
  - `refresh_tokens(db, refresh_token)` decodes with `expected_type="refresh"`, reloads the user, and issues a new pair.
  - `change_password` raises **400** (not 401) for a wrong current password. A 401 would make the frontend think the session expired and log the user out.
- `history.py`:
  - `record(...)` inserts a row.
  - `list_for_user` runs a `COUNT(*)` plus a page query, both filtered by `user_id`.
  - `delete_for_user` issues one `DELETE ... WHERE id = :id AND user_id = :me`. Zero rows deleted → `NotFoundError`, so other users' ids are indistinguishable from non-existent ones.
- `sql.py`:
  - **Imports:** `StrOutputParser` from `langchain_core.output_parsers`; the prompts; `extract_sql`; `LLMServiceError`.
  - `_run_chain(prompt, llm, inputs)` builds `prompt | llm | StrOutputParser()` (LCEL), calls `await chain.ainvoke(inputs)`, measures latency with `time.perf_counter()`, and turns any provider exception into `LLMServiceError` (→ 502). It also rejects empty responses.
  - `generate_sql` / `assist_sql` pick the template and post-process: fences are stripped for SQL modes, while explain keeps its markdown.
  - It returns an immutable `LLMResult` dataclass, not an HTTP response.

### 3.12 `app/api/deps.py`: dependencies
**Imports:** `Depends` from fastapi; `HTTPBearer, HTTPAuthorizationCredentials` from `fastapi.security`; `get_db`, `get_primary_llm`, `decode_token`, `User`.

- `bearer_scheme = HTTPBearer(auto_error=False)` reads the `Authorization: Bearer <token>` header. It also makes the **Authorize** button appear in Swagger UI. `auto_error=False` means we raise our own 401 with our envelope.
- `get_current_user(db, credentials)`: missing header → 401; otherwise decode with `expected_type="access"`, parse the UUID, load the user, and check `is_active`. Any failure becomes the same 401.
- Type aliases: `DbSession`, `CurrentUser`, `PrimaryLLM` (`Annotated[Type, Depends(fn)]`). Routes just declare `user: CurrentUser`.

### 3.13 `app/api/v1/routes/` + `router.py`
- `auth.py`: `POST /auth/signup` (201, `response_model=UserRead`), `POST /auth/login`, `POST /auth/refresh`.
- `users.py`: `GET/PATCH/DELETE /users/me`, `POST /users/me/password` (204).
- `sql.py`: `POST /sql/generate` and `POST /sql/assist` call the service, then (if `save_history`) write history **in the same request**, returning `LLMResponse` with `history_id`.
- `history.py`: `GET /history?limit=1..100&offset>=0` (validated by `Query(ge=, le=)`) and `DELETE /history/{entry_id}` (`uuid.UUID` path parameter, so malformed ids → 422).
- `health.py`: `/health/live` (process up) and `/health/ready` (runs `SELECT 1`; 503 if the DB is down).
- `router.py` combines them into `api_router`; `main.py` mounts it under `/api/v1`.

### 3.14 `app/main.py`: the application factory
- `lifespan(app)` is an async context manager. Code before `yield` runs at startup (logging setup); code after runs at shutdown (`engine.dispose()` closes pooled connections).
- `create_app()`: build `FastAPI(...)`, add `CORSMiddleware` (origins from settings), register exception handlers, mount `api_router`.
- `app = create_app()` is what `uvicorn app.main:app` loads. A factory makes it easy to build differently configured apps (tests, workers).

### 3.15 Alembic: `alembic.ini`, `alembic/env.py`, `alembic/versions/`
- `env.py` imports `app.models` (registers tables) and sets `target_metadata = Base.metadata`. It connects with `create_async_engine(settings.sqlalchemy_url, poolclass=NullPool)`, so the app and its migrations share one source of truth for the connection. Migrations run through `connection.run_sync(...)`.
  - The URL is deliberately **not** copied into Alembic's config with `config.set_main_option("sqlalchemy.url", ...)`. `alembic.ini` is read by Python's `ConfigParser`, which treats `%` as interpolation syntax, so a URL-encoded password (`%40` for `@`) would crash every migration.
- `compare_type=True` also detects column type changes. `render_as_batch` is enabled only for SQLite (which can't `ALTER` most things).
- `versions/2026_10_07_0001-3aea2b6b21c0_create_users_and_query_history.py` creates both tables and their indexes and has a full `downgrade()`.
  - It was autogenerated and then **hand-reviewed**: autogenerate ran against SQLite and produced SQLite-flavoured defaults, which we replaced with portable `CURRENT_TIMESTAMP`.
  - Verified with: `upgrade` → `alembic check` (no drift) → `downgrade base` → `upgrade`, plus `upgrade head --sql` to inspect the Postgres DDL.

### 3.16 Tests: `tests/`
- `conftest.py`:
  - Sets env vars **before** importing the app (`DATABASE_URL=sqlite+aiosqlite://`, a test JWT secret, a dummy Groq key).
  - The `session_factory` fixture creates an in-memory SQLite engine with `StaticPool` (one shared connection, so every session sees the same DB) and runs `create_all`.
  - The `client` fixture uses `app.dependency_overrides` to swap `get_db` → test sessions and `get_primary_llm` → `FakeListChatModel`. It then calls the app in-process via `httpx.AsyncClient(transport=ASGITransport(app))`, with no server or network.
- `test_auth.py` (12 tests) covers: hashing is salted, signup hides the password and normalizes email, duplicate → 409, short password → 422 with field details, wrong password ≡ unknown email, `/me` needs a token, a refresh token can't be used as an access token (and vice versa), refresh works, a validly signed token for a non-existent user is rejected, and password change works.
- `test_sql_and_history.py` (7 tests) covers: fence stripping, auth required, generate returns clean SQL **and** saves history, `save_history=false`, invalid mode → 422, an LLM outage → 502 envelope, and **history isolation between users** (an IDOR regression test).
- `test_config.py` (3 tests) covers: the URL is built from the `POSTGRES_*` fields (and its repr hides the password), a password like `p@ss:w/rd#1%` survives a render/parse round trip, and `DATABASE_URL` overrides the fields. It uses `Settings(_env_file=None, ...)` so your real `.env` never leaks into the test.
- `test_database_errors.py` (1 test): with an unreachable database (a SQLite file in a folder that doesn't exist, which fails at connect time like a wrong password does), signup returns **503 `database_unavailable`**, not a 500.

> Tests check *our plumbing* deterministically. *Model quality* is measured separately with evals (Phase 5).

---

## 4. Frontend changes

| File | Change |
|---|---|
| `src/lib/api.js` **(new)** | The only module that calls the backend. Base URL from `VITE_API_URL`. `tokens` helper (localStorage). `ApiError` mirrors the backend envelope. On 401 it refreshes once and retries; concurrent 401s share one refresh promise (`refreshInFlight ??= fetch(...)`). If refresh fails → clear tokens, go to `/login`. Exposes `api.signup/login/me/updateMe/changePassword/deleteAccount/generateSql/assistSql/listHistory/deleteHistory`. |
| `src/components/ProtectedRoute.jsx` **(new)** | Layout route: renders `<Outlet/>` if a token exists, else `<Navigate to="/login" state={{from}}/>`. A UX guard only; the backend's 401 is the real security. |
| `src/App.jsx` | Private pages wrapped in `<Route element={<ProtectedRoute/>}>`. |
| `src/loginPage.jsx` | Uses `api.login`. Inline error message, disabled button while submitting, and redirect back to the originally requested page. (Old bug: `if (response)` was always true, so it stored `undefined` as the token and navigated anyway.) |
| `src/signUpPage.jsx` | Added the missing **confirm password** field; checks match; `api.signup` then auto-login. (Old bug: success was checked as `status === 200`; signup now correctly returns 201.) |
| `src/queryBuilder.jsx` | `api.generateSql` with `saveHistory` bound to the “remember history” checkbox. |
| `src/sql_assistants.jsx` | `api.assistSql` (maps `debug-sql` → `debug`). The second `/add-query` call is removed; the backend saves history itself. (Old bug: `toString(Date.now())` called the *global* `toString`.) |
| `src/user_account.jsx` | Loads `api.me()` + real history (merged into state instead of replacing it, which used to wipe plan/bio). Save profile, change password and delete account now call the API. |
| `package.json` (frontend + root) | Frontend: removed the unused `@tailwindcss/vite` (v4 plugin next to Tailwind v3) and `concurrently`. Root: now only a runner (`npm run dev` starts API + web). |
| `.env.example` | `VITE_API_URL`. |

---

## 5. Request lifecycles, traced through the code

### Signup
1. `signUpPage.jsx` checks the two passwords match, then calls `api.signup(formData)`. `lib/api.js` sends `POST /api/v1/auth/signup` without a token (`auth: false`).
2. FastAPI matches the route in `routes/auth.py`, and Pydantic builds `SignupRequest`: the email is normalized, password length and bytes are checked (on failure: 422 via `exceptions.py`).
3. `Depends(get_db)` opens an `AsyncSession` from the pool.
4. `services/auth.register_user` runs `SELECT` by email (409 if it exists), then `hash_password`, `db.add(User)`, `commit()` → `INSERT`.
5. `response_model=UserRead` serializes the `User` object without the hash. Status is 201.
6. Back in the browser, `api.login(...)` stores both tokens and the user is navigated to `/querybuilder`.

### Generate SQL (authenticated)
1. `queryBuilder.jsx` calls `api.generateSql({question, dialect, saveHistory})`, which adds `Authorization: Bearer <access>`.
2. `routes/sql.generate` needs `CurrentUser`, `DbSession` and `PrimaryLLM`. FastAPI resolves them: `get_db` gives a session, `get_current_user` decodes the JWT and loads the user, and `get_primary_llm` returns the cached `ChatGroq`.
3. `services/sql.generate_sql`:
   - `GENERATE_SQL_PROMPT | llm | StrOutputParser()` is awaited.
   - Groq returns an `AIMessage`, the parser turns it into a string, and `extract_sql` strips the fences.
4. `history.record(...)` runs an `INSERT`. The response is `LLMResponse {output, model, latency_ms, history_id}`.
5. On a Groq failure the service raises `LLMServiceError` and the handler returns a 502 envelope. The UI shows `-- Error: <message>`.

### Expired access token
1. Some call returns 401. `lib/api.js` sees `res.status === 401 && retry && tokens.refresh`.
2. `refreshTokens()` sends `POST /auth/refresh`, and the server checks `type == "refresh"`. On success, the new pair is saved and the original request is retried once (`retry: false`).
3. If refresh fails, `endSession()` clears the tokens and redirects to `/login`.

---

## 6. Bugs fixed (root cause → fix)

| # | Symptom | Root cause | Fix |
|---|---|---|---|
| 1 | Every AI request failed | `llama3-70b-8192` deprecated by Groq | model ids in settings; `gpt-oss-120b` / `gpt-oss-20b` (checked against the live `/models` list) |
| 2 | History never saved | sync `def` route called async Motor methods without `await` (coroutines never ran) | Postgres + async SQLAlchemy; history written server-side inside the same request |
| 3 | Passwords readable in DB | stored and compared as plain text | bcrypt hash + constant-time check |
| 4 | Anyone could read any profile | `/user-data/{user_id}` had no auth; `verify_token` never used | `get_current_user` dependency; `/users/me`; owner-scoped queries |
| 5 | Frontend couldn't detect failures | errors returned with HTTP 200 | `AppError` hierarchy + handlers; proper status codes |
| 6 | One slow LLM call froze all users | sync Groq client inside `async def` | async LCEL `ainvoke` |
| 7 | Project couldn't be installed | empty `requirements.txt` | `pyproject.toml` + `uv.lock` (+ export) |
| 8 | Weak token signing | 13-char JWT secret | 48-byte random secret; config enforces ≥ 32 chars |
| 9 | Unmaintained auth lib | python-jose | PyJWT with algorithm pinning + required claims + `type` claim |
| 10 | Explain mode unreliable | system prompt said “output only SQL” for explanations | one template per mode |
| 11 | Login “succeeded” on failure | `if (response)` is always truthy for a JSON body | `ApiError` on non-2xx; inline error |
| 12 | Signup UI never confirmed success | expected 200, no confirm-password field | 201 handling, confirm field, auto-login |
| 13 | Broken query ids | global `toString(Date.now())` | ids come from the DB (UUID) |
| 14 | Profile lost plan/bio | `setUserData(data)` replaced the whole object | merge: `setUserData(prev => ({...prev, ...}))` |
| 15 | Hard to deploy | `localhost` URLs in 5 files, hard-coded CORS | `VITE_API_URL`, `CORS_ORIGINS` |
| 16 | Private pages visible when logged out | no route guard | `ProtectedRoute` |
| 17 | Fragile frontend build | duplicate `package.json`s; `jwt-decode` only at root; Tailwind v3 + v4 plugin | one manifest per app; unused deps removed |

---

## 7. Run & verify locally

First, a database. Either use your local PostgreSQL: in pgAdmin's Query Tool, run `CREATE ROLE sqlassist WITH LOGIN PASSWORD '...';` and then, separately, `CREATE DATABASE sql_assistant OWNER sqlassist;`. Or start Docker:

```bash
docker compose up -d
```

That gives Postgres on 5433 (`postgres`/`postgres`) and Qdrant on 6333.

```bash
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --reload-include .env --port 8000
```

Before running these, fill the `POSTGRES_*` values in `backend/.env`. Local install: `localhost`, `5432`, your role and password. Docker: `localhost`, `5433`, `postgres`, `postgres`. After `alembic upgrade head`, pgAdmin shows `users`, `query_history` and `alembic_version` under *sql_assistant → Schemas → public → Tables*.

```bash
uv run pytest -q
```

That should report 23 passed. Then:

- Open <http://localhost:8000/docs>: sign up, log in, click **Authorize**, paste the access token, and try `/sql/generate`.
- Frontend: `cd frontend && npm run dev`, then <http://localhost:5173>.

---

## 8. Interview questions you can now answer

1. **Hashing vs encryption for passwords?** Hashing is one-way; we only need to *check* a password, never recover it. Encryption is reversible by whoever has the key.
2. **What does a salt protect against?** Precomputed rainbow tables, and identical passwords producing identical hashes.
3. **Why bcrypt and not SHA-256?** bcrypt is deliberately slow with a tunable cost; SHA-256 is fast, which helps attackers brute-force.
4. **Is a JWT encrypted?** No. It's signed. The payload is base64url, readable by anyone; the signature only prevents tampering.
5. **Why access *and* refresh tokens?** Short-lived access limits damage if stolen; the refresh token is used rarely, on one endpoint.
6. **How do you revoke a JWT early?** A `jti` denylist (e.g. Redis), refresh-token rotation with reuse detection, or a per-user token version.
7. **What is IDOR and how did we fix it?** Trusting ids from the client. Fix: identity comes from the verified token, and every query is filtered by owner (404 for foreign rows).
8. **401 vs 403?** Not authenticated vs authenticated but not allowed.
9. **Why 422 for validation errors?** The syntax is fine (it's JSON) but the content violates the schema: “Unprocessable Content”.
10. **What does async buy you in FastAPI?** One thread serves many concurrent requests while they wait on I/O. Blocking calls inside `async def` destroy that.
11. **What is dependency injection, and how do tests use it?** Functions declare needs and the framework provides them; tests override `get_db` and the LLM provider.
12. **Why a connection pool?** Opening Postgres connections is expensive; pooling reuses them.
13. **What does `expire_on_commit=False` do and why do we need it with async?** It keeps attributes loaded after commit, avoiding implicit lazy IO, which async sessions can't do.
14. **Why migrations instead of `create_all()`?** Versioned, reviewable, reversible changes that apply consistently to every environment.
15. **Why should you review autogenerated migrations?** Autogenerate is a diff guess: it can render dialect-specific defaults, miss renames (it sees a drop + add), etc.
16. **Composite index `(user_id, created_at)`: which queries use it?** Those filtering on `user_id` (optionally sorted/filtered by `created_at`), not those on `created_at` alone (leftmost-prefix rule).
17. **What is LCEL?** LangChain's `|` composition of Runnables; each step's output feeds the next, with sync/async/stream/batch for free.
18. **How do you unit-test LLM code deterministically?** Fake chat models with scripted outputs; measure real quality with evals.
19. **What happens if the LLM provider is down?** Retries with backoff (`max_retries`), a timeout, then a domain error → 502 with a clear message.
20. **Why is CORS not a security boundary for your API?** It's enforced by browsers for users' protection; non-browser clients ignore it. Auth is the boundary.

---

## 9. Known gaps and leftovers (carried into later phases)

- **Delete the legacy backend files** (not imported anywhere): `backend/app/auth.py`, `backend/app/database/`, `backend/app/routes/`, and the committed `backend/app/**/__pycache__/` folders. Also `frontend/utils/decode_user_id.jsx` (replaced by `/users/me`).
- ESLint flags `motion` as unused in some pages: the config lacks a JSX-aware rule for `<motion.div>`. To fix in the UI phase.
- Tokens live in `localStorage`. Phase 8 moves the refresh token to an httpOnly cookie and adds revocation.
- No rate limiting yet (Groq free-tier limits apply). Phase 8.
- Email change needs a verification flow. Only the name is editable today.
- Tests run on SQLite; a few behaviours differ from Postgres (e.g. SQLite returns timezone-naive datetimes). Phase 9 CI adds a Postgres service container.
- The LLM still **doesn't see the user's schema**. That's the whole point of Phases 2–4.
