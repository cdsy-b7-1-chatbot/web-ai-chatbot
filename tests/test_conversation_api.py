from datetime import UTC, datetime

from sqlalchemy.exc import SQLAlchemyError

from app.chat import repository
from app.db.models import User


def test_room_list_requires_login(client):
    assert client.get("/api/conversations").status_code == 401


def test_empty_room_list_works_without_ai_key(client, auth_headers):
    response = client.get("/api/conversations", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == {"items": []}


def test_list_is_private_sorted_and_has_only_public_fields(client, auth_headers, db, user):
    first = repository.create_conversation(db, user.id, "첫 방")
    second = repository.create_conversation(db, user.id, "둘째 방")
    newest = repository.create_conversation(db, user.id, "최신 활동")
    first.updated_at = second.updated_at = datetime(2000, 1, 1, tzinfo=UTC)
    newest.updated_at = datetime(2001, 1, 1, tzinfo=UTC)
    other = User(username="other", password_hash="private-hash")
    db.add(other)
    db.commit()
    repository.create_conversation(db, other.id, "다른 사용자의 방")
    response = client.get("/api/conversations", headers=auth_headers)
    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["id"] for item in items] == [newest.id, second.id, first.id]
    assert set(items[0]) == {"id", "title", "created_at", "updated_at"}
    assert all(item["created_at"].endswith("Z") for item in items)
    assert all(item["updated_at"].endswith("Z") for item in items)


def test_room_list_db_error_is_safe(client, auth_headers, monkeypatch, caplog):
    def fail(*args, **kwargs):
        raise SQLAlchemyError("private-db-url")

    monkeypatch.setattr(repository, "list_conversations", fail)
    response = client.get("/api/conversations", headers=auth_headers)
    assert response.status_code == 500
    assert response.json()["error"] == "DB_ERROR"
    assert "db_read_failed" in caplog.text
    assert "private-db-url" not in response.text + caplog.text
