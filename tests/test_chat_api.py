import pytest
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.chat import repository
from app.chat.client import AIClientError, AIResult, get_ai_client
from app.db.models import Chat, Conversation, User


class FakeAI:
    def __init__(self):
        self.messages = []
        self.error = None
        self.result = AIResult("답변", "qwen/test", 10, 20, False)

    def ensure_configured(self):
        pass

    async def generate(self, messages):
        self.messages.append(messages)
        if self.error:
            raise AIClientError(self.error)
        return self.result


@pytest.fixture
def fake_ai(client):
    ai = FakeAI()
    client.app.dependency_overrides[get_ai_client] = lambda: ai
    return ai


def test_new_chat_is_saved_before_success_response(client, auth_headers, fake_ai, db, user):
    response = client.post("/api/chat", headers=auth_headers, json={"question": "  배포 방법  "})
    assert response.status_code == 200
    body = response.json()
    saved = db.get(Chat, body["chat_id"])
    room = db.get(Conversation, body["conversation_id"])
    assert saved.user_id == user.id == room.user_id
    assert (saved.question, saved.answer, saved.status) == ("배포 방법", "답변", "success")
    assert (saved.input_tokens, saved.output_tokens) == (10, 20)
    assert room.title == "배포 방법"
    assert body["created_at"].endswith("Z")
    assert body["truncated"] is False
    assert len(fake_ai.messages[0]) == 2


def test_followup_keeps_the_room_and_prior_answer(client, auth_headers, fake_ai):
    first = client.post("/api/chat", headers=auth_headers, json={"question": "처음 질문"}).json()
    second = client.post(
        "/api/chat",
        headers=auth_headers,
        json={
            "question": "방금 뭘 물었지?",
            "conversation_id": first["conversation_id"],
        },
    )
    assert second.status_code == 200
    assert second.json()["conversation_id"] == first["conversation_id"]
    assert [m["content"] for m in fake_ai.messages[-1][1:]] == [
        "처음 질문",
        "답변",
        "방금 뭘 물었지?",
    ]


def test_anonymous_user_cannot_call_ai(client, fake_ai):
    assert client.post("/api/chat", json={"question": "질문"}).status_code == 401
    assert fake_ai.messages == []


@pytest.mark.parametrize("question", ["", " \n ", "가" * 5001])
def test_bad_input_never_calls_ai(client, auth_headers, fake_ai, question):
    response = client.post("/api/chat", headers=auth_headers, json={"question": question})
    assert response.status_code == 422
    assert response.json()["error"] == "VALIDATION_ERROR"
    assert fake_ai.messages == []


def test_other_user_and_missing_room_are_not_found(client, auth_headers, fake_ai, db):
    other = User(username="other-user", password_hash="hash")
    db.add(other)
    db.commit()
    room = repository.create_conversation(db, other.id, "다른 사용자의 방")
    for room_id in (room.id, 99999):
        response = client.post(
            "/api/chat", headers=auth_headers, json={"question": "질문", "conversation_id": room_id}
        )
        assert response.status_code == 404
    assert fake_ai.messages == []


def test_missing_ai_key_keeps_auth_and_health_available(client, auth_headers, db):
    response = client.post("/api/chat", headers=auth_headers, json={"question": "질문"})
    assert response.status_code == 503
    assert response.json()["error"] == "AI_NOT_CONFIGURED"
    assert list(db.scalars(select(Conversation))) == []
    assert client.get("/api/auth/me", headers=auth_headers).status_code == 200
    assert client.get("/api/health").status_code == 200


@pytest.mark.parametrize(("error", "status"), [("AI_TIMEOUT", 504), ("AI_ERROR", 502)])
def test_ai_failure_is_saved_without_an_answer(client, auth_headers, fake_ai, db, error, status):
    fake_ai.error = error
    response = client.post("/api/chat", headers=auth_headers, json={"question": "실패 질문"})
    assert response.status_code == status
    assert response.json()["error"] == error
    saved = db.scalar(select(Chat))
    assert saved.status == "failed"
    assert saved.question == "실패 질문"
    assert saved.answer is None
    assert saved.error_code == error
    assert saved.input_tokens is None
    assert client.get("/api/health").status_code == 200


def test_save_failure_hides_generated_answer(client, auth_headers, fake_ai, monkeypatch):
    def fail(*args, **kwargs):
        raise SQLAlchemyError("private-db-password")

    monkeypatch.setattr(repository, "save_chat", fail)
    response = client.post("/api/chat", headers=auth_headers, json={"question": "질문"})
    assert response.status_code == 500
    assert response.json()["error"] == "DB_ERROR"
    assert "답변" not in response.text
    assert "private-db-password" not in response.text
    assert len(fake_ai.messages) == 1


def test_failed_ai_then_failed_save_returns_db_error(
    client, auth_headers, fake_ai, monkeypatch, caplog
):
    fake_ai.error = "AI_TIMEOUT"

    def fail(*args, **kwargs):
        raise SQLAlchemyError("private-db-password")

    monkeypatch.setattr(repository, "save_chat", fail)
    response = client.post("/api/chat", headers=auth_headers, json={"question": "질문"})
    assert response.status_code == 500
    assert response.json()["error"] == "DB_ERROR"
    assert "error_code=AI_TIMEOUT" in caplog.text


def test_db_read_failure_does_not_call_ai(client, auth_headers, fake_ai, conversation, monkeypatch):
    def fail(*args, **kwargs):
        raise SQLAlchemyError("private-db-password")

    monkeypatch.setattr(repository, "get_recent_chats", fail)
    response = client.post(
        "/api/chat",
        headers=auth_headers,
        json={
            "question": "질문",
            "conversation_id": conversation.id,
        },
    )
    assert response.status_code == 500
    assert response.json()["error"] == "DB_ERROR"
    assert fake_ai.messages == []
