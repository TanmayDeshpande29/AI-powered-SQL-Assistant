from sqlalchemy.engine import URL, make_url

from app.core.config import Settings

REQUIRED = {"jwt_secret_key": "x" * 40, "groq_api_key": "test"}


def make_settings(**overrides) -> Settings:
    # _env_file=None: ignore backend/.env so the test only sees what it passes in.
    return Settings(_env_file=None, **REQUIRED, **overrides)


def test_url_is_built_from_postgres_fields():
    settings = make_settings(
        database_url=None,
        postgres_host="db.internal",
        postgres_port=5544,
        postgres_user="sqlassist",
        postgres_password="secret",
        postgres_db="sql_assistant",
    )
    url = settings.sqlalchemy_url
    assert isinstance(url, URL)
    assert url.drivername == "postgresql+asyncpg"
    assert (url.host, url.port, url.username, url.database) == (
        "db.internal",
        5544,
        "sqlassist",
        "sql_assistant",
    )
    assert "secret" not in repr(url)  # password is masked when logged


def test_special_characters_in_password_survive_round_trip():
    tricky = "p@ss:w/rd#1%"  # every one of these breaks a hand-written URL
    settings = make_settings(database_url=None, postgres_password=tricky, postgres_host="db")
    rendered = settings.sqlalchemy_url.render_as_string(hide_password=False)
    parsed = make_url(rendered)
    assert parsed.password == tricky
    assert parsed.host == "db"  # the "@" in the password did not confuse host parsing


def test_database_url_overrides_individual_fields():
    settings = make_settings(database_url="sqlite+aiosqlite://", postgres_host="ignored")
    assert settings.sqlalchemy_url == "sqlite+aiosqlite://"
