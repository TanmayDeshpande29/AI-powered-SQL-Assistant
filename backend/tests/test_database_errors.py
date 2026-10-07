from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db import session as session_module
from app.db.session import get_db
from app.main import app


async def test_unreachable_database_returns_clear_503(client, monkeypatch, tmp_path):
    # A SQLite file inside a folder that does not exist: connecting fails immediately,
    # exactly like a wrong password or a stopped PostgreSQL server would.
    missing = (tmp_path / "missing-dir" / "app.db").as_posix()
    broken_engine = create_async_engine(f"sqlite+aiosqlite:///{missing}")
    monkeypatch.setattr(session_module, "SessionLocal", async_sessionmaker(broken_engine))
    app.dependency_overrides.pop(get_db)  # use the real get_db for this one test

    res = await client.post(
        "/api/v1/auth/signup",
        json={"name": "Ada", "email": "ada@example.com", "password": "s3cret-pass"},
    )

    assert res.status_code == 503
    assert res.json()["error"]["code"] == "database_unavailable"
    await broken_engine.dispose()
