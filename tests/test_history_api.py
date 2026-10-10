from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.auth.security import ACCESS_TOKEN_COOKIE, create_access_token
from app.chat import repository as chat_repository
from app.db.models import Chat, User
from app.history import repository, service


@pytest.fixture
def records(db, user, conversation):
    second_room = chat_repository.create_conversation(db, user.id, "둘째 방")
    other = User(username="other", password_hash="private-hash")
    db.add(other)
    db.flush()
    other_room = chat_repository.create_conversation(db, other.id, "다른 사용자 방")
    older = datetime(2026, 10, 1, tzinfo=UTC)
    newer = datetime(2026, 10, 2, tzinfo=UTC)
    entries = [
        Chat(
            user_id=user.id,
            conversation_id=conversation.id,
            question="첫 질문",
            answer="첫 답변",
            status="success",
            created_at=older,
        ),
        Chat(
            user_id=user.id,
            conversation_id=conversation.id,
            question="실패 질문",
            answer=None,
            status="failed",
            error_code="AI_TIMEOUT",
            created_at=newer,
        ),
        Chat(
            user_id=user.id,
            conversation_id=second_room.id,
            question="둘째 방 질문",
            answer="둘째 답변",
            status="success",
            created_at=newer,
        ),
        Chat(
            user_id=other.id,
            conversation_id=other_room.id,
            question="비공개 질문",
            answer="비공개 답변",
            status="success",
            created_at=newer,
        ),
    ]
    db.add_all(entries)
    db.commit()
    return entries


def test_history_requires_login(client):
    response = client.get("/api/me/chats")
    assert response.status_code == 401
    assert response.json()["error"] == "UNAUTHORIZED"


def test_empty_history_works_without_ai_key(client, auth_headers):
    response = client.get("/api/me/chats", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == {"items": []}


def test_history_uses_existing_cookie_auth(client, user):
    client.cookies.set(ACCESS_TOKEN_COOKIE, create_access_token(user.id))
    response = client.get("/api/me/chats")
    assert response.status_code == 200


def test_history_is_private_sorted_and_includes_failures(client, auth_headers, user, records):
    response = client.get(
        "/api/me/chats", headers=auth_headers, params={"user_id": records[3].user_id}
    )
    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["id"] for item in items] == [records[2].id, records[1].id, records[0].id]
    assert all(item["user_id"] == user.id for item in items)
    assert set(items[0]) == {
        "id",
        "user_id",
        "conversation_id",
        "question",
        "answer",
        "status",
        "error_code",
        "created_at",
    }
    assert all(item["created_at"].endswith("Z") for item in items)
    assert items[1]["status"] == "failed"
    assert items[1]["answer"] is None
    assert items[1]["error_code"] == "AI_TIMEOUT"
    assert items[2]["question"] == "첫 질문"
    assert items[2]["answer"] == "첫 답변"
    assert "비공개" not in response.text


def test_selected_room_returns_only_its_records(client, auth_headers, conversation, records):
    response = client.get(
        "/api/me/chats", headers=auth_headers, params={"conversation_id": conversation.id}
    )
    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == [records[1].id, records[0].id]


def test_owned_empty_room_returns_empty_list(client, auth_headers, conversation):
    response = client.get(
        "/api/me/chats", headers=auth_headers, params={"conversation_id": conversation.id}
    )
    assert response.status_code == 200
    assert response.json() == {"items": []}


def test_other_user_and_missing_rooms_have_the_same_error(client, auth_headers, records):
    responses = [
        client.get("/api/me/chats", headers=auth_headers, params={"conversation_id": room_id})
        for room_id in (records[3].conversation_id, 99999)
    ]
    assert all(response.status_code == 404 for response in responses)
    assert (
        responses[0].json()
        == responses[1].json()
        == {"error": "NOT_FOUND", "message": "대화방을 찾을 수 없습니다."}
    )


def test_pagination_applies_after_user_and_room_filters(client, auth_headers, records):
    response = client.get("/api/me/chats", headers=auth_headers, params={"limit": 2, "offset": 1})
    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == [records[1].id, records[0].id]
    response = client.get(
        "/api/me/chats",
        headers=auth_headers,
        params={"conversation_id": records[0].conversation_id, "limit": 1, "offset": 1},
    )
    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == [records[0].id]
    response = client.get("/api/me/chats", headers=auth_headers, params={"offset": 99})
    assert response.json() == {"items": []}


def test_default_limit_and_maximum_limit(client, auth_headers, db, user, conversation):
    db.add_all(
        Chat(
            user_id=user.id,
            conversation_id=conversation.id,
            question=str(i),
            answer="답변",
            status="success",
        )
        for i in range(101)
    )
    db.commit()
    assert len(client.get("/api/me/chats", headers=auth_headers).json()["items"]) == 50
    response = client.get("/api/me/chats", headers=auth_headers, params={"limit": 100})
    assert response.status_code == 200
    assert len(response.json()["items"]) == 100


@pytest.mark.parametrize(
    "params",
    [
        {"limit": 0},
        {"limit": 101},
        {"limit": -1},
        {"limit": "wrong"},
        {"offset": -1},
        {"offset": "wrong"},
        {"conversation_id": 0},
        {"conversation_id": -1},
        {"conversation_id": "wrong"},
    ],
)
def test_invalid_query_is_rejected(client, auth_headers, params):
    response = client.get("/api/me/chats", headers=auth_headers, params=params)
    assert response.status_code == 422
    assert response.json()["error"] == "VALIDATION_ERROR"


@pytest.mark.parametrize("operation", ["list_chats", "get_conversation"])
def test_db_failure_is_safe(client, auth_headers, conversation, monkeypatch, caplog, operation):
    def fail(*args, **kwargs):
        raise SQLAlchemyError("private-db-url")

    target = repository if operation == "list_chats" else service
    monkeypatch.setattr(target, operation, fail)
    response = client.get(
        "/api/me/chats", headers=auth_headers, params={"conversation_id": conversation.id}
    )
    assert response.status_code == 500
    assert response.json()["error"] == "DB_ERROR"
    assert "db_read_failed" in caplog.text
    assert "private-db-url" not in response.text + caplog.text
    assert client.get("/api/health").status_code == 200


def test_reading_history_preserves_saved_logs(client, auth_headers, db, records):
    before = [(row.id, row.question, row.answer, row.status) for row in db.scalars(select(Chat))]
    assert client.get("/api/me/chats", headers=auth_headers).status_code == 200
    db.expire_all()
    after = [(row.id, row.question, row.answer, row.status) for row in db.scalars(select(Chat))]
    assert after == before


def test_history_is_documented_in_openapi(client):
    spec = client.get("/openapi.json").json()
    operation = spec["paths"]["/api/me/chats"]["get"]
    params = {item["name"]: item["schema"] for item in operation["parameters"]}
    assert params["limit"]["default"] == 50
    assert params["limit"]["maximum"] == 100
    assert params["offset"]["minimum"] == 0
    assert operation["security"]
    assert {"200", "401", "404", "422", "500"} <= operation["responses"].keys()
    for status in ("401", "404", "422", "500"):
        assert operation["responses"][status]["content"]["application/json"]["schema"] == {
            "$ref": "#/components/schemas/ErrorResponse"
        }
