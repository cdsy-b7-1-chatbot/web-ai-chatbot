import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect

from app.core.config import Settings
from app.db import database
from app.main import create_app


@pytest.fixture
def database_url(monkeypatch):
    def use(url):
        monkeypatch.setattr(
            database, "get_settings", lambda: Settings(_env_file=None, database_url=url)
        )
        database.get_engine.cache_clear()

    yield use
    database.get_engine.cache_clear()


def test_startup_creates_tables(database_url, tmp_path):
    database_url(f"sqlite:///{tmp_path / 'app.db'}")

    with TestClient(create_app()) as client:
        assert client.get("/api/health").status_code == 200
        tables = set(inspect(database.get_engine()).get_table_names())

    assert tables == {"users", "conversations", "chats"}


def test_startup_stops_without_database_url(database_url):
    database_url(None)

    with pytest.raises(RuntimeError, match="DATABASE_URL"), TestClient(create_app()):
        pass
