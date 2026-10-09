import json
import logging

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.chat.client import OpenRouterClient, get_ai_client
from app.core.config import get_settings
from app.db.models import Chat, Conversation


def install_ai(client, configure, handler):
    configure(openrouter_api_key="test-only-private-key")
    ai = OpenRouterClient(get_settings(), transport=httpx.MockTransport(handler))
    client.app.dependency_overrides[get_ai_client] = lambda: ai


def completion(answer="private-answer", reason="stop"):
    return httpx.Response(
        200,
        json={
            "model": "qwen/qwen3-30b-a3b-instruct-2507",
            "choices": [{"message": {"content": answer}, "finish_reason": reason}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        },
    )


def events(caplog):
    return [record.getMessage() for record in caplog.records if record.name.startswith("app.")]


def test_success_pipeline_shares_request_id_and_never_logs_secrets(
    client, configure, auth_headers, user, caplog
):
    caplog.set_level(logging.INFO)

    def handler(request):
        payload = json.loads(request.content)
        assert payload["provider"] == {"only": ["streamlake"], "allow_fallbacks": False}
        return completion(reason="length")

    install_ai(client, configure, handler)
    response = client.post("/api/chat", headers=auth_headers, json={"question": "private-question"})
    assert response.status_code == 200
    assert response.json()["truncated"] is True
    logs = events(caplog)
    required = ["request_received", "ai_call_start", "ai_call_success", "db_save_success"]
    for event in required:
        line = next(line for line in logs if line.startswith(event + " "))
        assert f"request_id={response.headers['X-Request-ID']}" in line
        assert f"user_id={user.id}" in line
    text = "\n".join(logs)
    for secret in (
        "test-only-private-key",
        "private-question",
        "private-answer",
        auth_headers["Authorization"],
    ):
        assert secret not in text


@pytest.mark.parametrize("fail_ai", [False, True])
def test_real_repository_save_failure_logs_both_causes_and_rolls_back(
    client, configure, auth_headers, monkeypatch, caplog, db, fail_ai
):
    caplog.set_level(logging.INFO)
    install_ai(
        client,
        configure,
        lambda request: (
            httpx.Response(502, text="private-upstream-error") if fail_ai else completion()
        ),
    )
    original_flush = Session.flush

    def fail_chat_flush(session, *args, **kwargs):
        if any(isinstance(row, Chat) for row in session.new):
            raise SQLAlchemyError("private-db-error")
        return original_flush(session, *args, **kwargs)

    monkeypatch.setattr(Session, "flush", fail_chat_flush)
    response = client.post("/api/chat", headers=auth_headers, json={"question": "private-question"})
    assert response.status_code == 500
    assert response.json()["error"] == "DB_ERROR"
    assert list(db.scalars(select(Chat))) == []
    assert len(list(db.scalars(select(Conversation)))) == 1
    logs = "\n".join(events(caplog))
    assert "db_save_failed" in logs
    assert ("ai_call_failed" if fail_ai else "ai_call_success") in logs
    assert "private-db-error" not in logs + response.text
    assert "private-upstream-error" not in logs + response.text
    assert "private-answer" not in response.text


def test_http_failure_is_saved_and_next_context_skips_it(client, configure, auth_headers, db):
    calls = []

    def handler(request):
        calls.append(json.loads(request.content)["messages"])
        if len(calls) == 2:
            return httpx.Response(429, text="private-upstream-error")
        return completion("답변")

    install_ai(client, configure, handler)
    first = client.post("/api/chat", headers=auth_headers, json={"question": "첫 질문"}).json()
    room_id = first["conversation_id"]
    failed = client.post(
        "/api/chat",
        headers=auth_headers,
        json={"question": "실패 질문", "conversation_id": room_id},
    )
    assert failed.status_code == 502
    saved = db.scalar(select(Chat).where(Chat.status == "failed"))
    assert saved.answer is None and saved.error_code == "AI_ERROR"
    for index in range(6):
        response = client.post(
            "/api/chat",
            headers=auth_headers,
            json={"question": f"후속 {index}", "conversation_id": room_id},
        )
        assert response.status_code == 200
    # 최신 성공 다섯 쌍 + 현재 질문. 첫 질문과 실패 질문은 빠진다.
    assert [message["content"] for message in calls[-1][1:]] == [
        "후속 0",
        "답변",
        "후속 1",
        "답변",
        "후속 2",
        "답변",
        "후속 3",
        "답변",
        "후속 4",
        "답변",
        "후속 5",
    ]


def test_timeout_has_request_trace_failed_record_and_healthy_next_request(
    client, configure, auth_headers, caplog, db
):
    caplog.set_level(logging.INFO)

    def handler(request):
        raise httpx.ReadTimeout("private-timeout-error", request=request)

    install_ai(client, configure, handler)
    response = client.post("/api/chat", headers=auth_headers, json={"question": "private-question"})
    assert response.status_code == 504
    assert response.json()["error"] == "AI_TIMEOUT"
    for event in ("ai_call_start", "ai_call_failed", "db_save_success"):
        line = next(line for line in events(caplog) if line.startswith(event + " "))
        assert f"request_id={response.headers['X-Request-ID']}" in line
    assert db.scalar(select(Chat)).status == "failed"
    assert client.get("/api/health").status_code == 200
    assert "private-timeout-error" not in "\n".join(events(caplog)) + response.text


def test_new_room_creation_failure_does_not_call_ai(client, configure, auth_headers, monkeypatch):
    calls = []

    def handler(request):
        calls.append(request)
        return completion()

    install_ai(client, configure, handler)

    original_flush = Session.flush

    def fail_flush(session, *args, **kwargs):
        if any(isinstance(row, Conversation) for row in session.new):
            raise SQLAlchemyError("private-db-error")
        return original_flush(session, *args, **kwargs)

    monkeypatch.setattr(Session, "flush", fail_flush)
    response = client.post("/api/chat", headers=auth_headers, json={"question": "질문"})
    assert response.status_code == 500
    assert response.json()["error"] == "DB_ERROR"
    assert calls == []


def test_chat_openapi_declares_examples_and_error_models(client):
    spec = client.get("/openapi.json").json()
    schemas = spec["components"]["schemas"]
    for name in ("ChatRequest", "ChatResponse", "ConversationListResponse"):
        assert schemas[name]["examples"]
    question = schemas["ChatRequest"]["properties"]["question"]
    assert (question["minLength"], question["maxLength"]) == (1, 5000)
    for path, method, codes in (
        ("/api/chat", "post", [401, 404, 422, 500, 502, 503, 504]),
        ("/api/conversations", "get", [401, 500]),
    ):
        for code in codes:
            response_schema = spec["paths"][path][method]["responses"][str(code)]["content"][
                "application/json"
            ]["schema"]
            assert response_schema == {"$ref": "#/components/schemas/ErrorResponse"}
