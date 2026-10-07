import logging

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db import database
from app.db.database import create_db_engine, init_db, normalize_database_url


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("postgres://u:p@host/db", "postgresql+psycopg://u:p@host/db"),
        ("postgresql://u:p@host/db", "postgresql+psycopg://u:p@host/db"),
        ("postgresql+psycopg://u:p@host/db", "postgresql+psycopg://u:p@host/db"),
        ("sqlite://", "sqlite://"),
    ],
)
def test_render_url_is_converted_for_psycopg3(url, expected):
    assert normalize_database_url(url) == expected


@pytest.fixture
def settings_with(monkeypatch):
    """.env 파일을 읽지 않는 설정으로 바꿔 끼운다(개발자 로컬 .env 의 영향을 받지 않게)."""

    def use(database_url):
        monkeypatch.setattr(
            database, "get_settings", lambda: Settings(_env_file=None, database_url=database_url)
        )
        database.get_engine.cache_clear()
        database._session_factory.cache_clear()

    yield use
    database.get_engine.cache_clear()
    database._session_factory.cache_clear()


def test_missing_database_url_stops_with_guidance(settings_with):
    settings_with(None)

    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        database.get_engine()


def test_get_db_yields_session_and_closes_it(settings_with, empty_database_url):
    settings_with(empty_database_url)

    dependency = database.get_db()
    session = next(dependency)

    assert isinstance(session, Session)
    assert session.execute(text("SELECT 1")).scalar() == 1
    dependency.close()


def test_sqlite_foreign_keys_are_enforced():
    engine = create_db_engine("sqlite://")

    with engine.connect() as conn:
        assert conn.execute(text("PRAGMA foreign_keys")).scalar() == 1


def test_init_db_logs_dialect_but_not_url(caplog):
    caplog.set_level(logging.INFO)
    engine = create_db_engine("sqlite:///:memory:")

    init_db(engine)

    [message] = [m for m in caplog.messages if m.startswith("db_ready")]
    assert "dialect=sqlite" in message
    assert "memory" not in message
