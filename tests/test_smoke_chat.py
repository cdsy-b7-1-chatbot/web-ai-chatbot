import json
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from app.chat.client import AIResult, get_ai_client
from scripts import smoke_chat


@pytest.fixture
def smoke_ai(client, monkeypatch):
    ai = SimpleNamespace(
        ensure_configured=lambda: None,
        generate=AsyncMock(return_value=AIResult("파란별", "test-model", 10, 3, False)),
    )
    client.app.dependency_overrides[get_ai_client] = lambda: ai
    # 실제 FastAPI·인증·테스트 DB를 통과하며 외부 서버와 AI에는 접속하지 않는다.
    monkeypatch.setattr(smoke_chat.httpx, "Client", lambda **kwargs: nullcontext(client))
    return ai


def test_smoke_checks_saved_history_and_relogin_without_extra_ai_calls(client, smoke_ai):
    result = smoke_chat.smoke("https://testserver")

    assert result["context_verified"] is True
    assert result["history_verified"] is True
    assert result["logout_verified"] is True
    assert result["relogin_history_verified"] is True
    assert len(set(result["chat_ids"])) == 2
    assert len(result["request_ids"]) == 2
    assert smoke_ai.generate.await_count == 2
    assert client.get("/api/me/chats").status_code == 401
    output = json.dumps(result)
    for field in ("username", "password", "access_token", "question", "answer"):
        assert field not in result
    assert "Bearer " not in output


@pytest.mark.parametrize(
    ("field", "value", "phase", "message"),
    [
        ("user_id", 999999, 1, "사용자·대화방"),
        ("answer", "저장되지 않은 답변", 1, "질문·응답"),
        ("status", "failed", 1, "질문·응답"),
        ("created_at", "2026-10-15T00:00:00", 1, "생성 시각"),
        ("items", [], 2, "기록 ID"),
    ],
)
def test_smoke_rejects_incorrect_or_lost_history(
    client, smoke_ai, monkeypatch, field, value, phase, message
):
    original_get = client.get
    history_reads = 0

    def incorrect_history(url, **kwargs):
        nonlocal history_reads
        response = original_get(url, **kwargs)
        if url == "/api/me/chats" and response.status_code == 200:
            history_reads += 1
            if history_reads == phase:
                body = response.json()
                if field == "items":
                    body["items"] = value
                else:
                    body["items"][0][field] = value
                return httpx.Response(200, json=body, request=response.request)
        return response

    monkeypatch.setattr(client, "get", incorrect_history)
    with pytest.raises(RuntimeError, match=message):
        smoke_chat.smoke("https://testserver")
    assert smoke_ai.generate.await_count == 2
