import asyncio
import json
import logging

import httpx
import pytest

from app.chat.client import OPENROUTER_URL, AIClientError, OpenRouterClient
from app.core.config import Settings

MESSAGES = [{"role": "user", "content": "질문"}]


def completion(**extra):
    return {
        "choices": [{"message": {"content": " 답변 "}, "finish_reason": "stop"}],
        "model": "qwen/test",
        "usage": {"prompt_tokens": 30, "completion_tokens": 12},
    } | extra


def call_client(handler, **settings):
    client = OpenRouterClient(
        Settings(openrouter_api_key="test-secret", **settings),
        transport=httpx.MockTransport(handler),
    )
    return asyncio.run(client.generate(MESSAGES))


def test_request_uses_model_provider_limit_and_private_key():
    def handle(request):
        assert str(request.url) == OPENROUTER_URL
        assert request.headers["authorization"] == "Bearer test-secret"
        assert "http-referer" not in request.headers
        assert "x-openrouter-title" not in request.headers
        body = json.loads(request.content)
        assert body == {
            "model": "qwen/qwen3-30b-a3b-instruct-2507",
            "messages": MESSAGES,
            "stream": False,
            "max_tokens": 1024,
            "provider": {"only": ["streamlake"], "allow_fallbacks": False},
        }
        return httpx.Response(200, json=completion())

    result = call_client(handle)
    assert result.answer == "답변"
    assert (result.input_tokens, result.output_tokens) == (30, 12)
    assert result.model == "qwen/test"
    assert not result.truncated


def test_optional_headers_are_only_sent_when_configured():
    def handle(request):
        assert request.headers["http-referer"] == "https://example.test"
        assert request.headers["x-openrouter-title"] == "Chatbot"
        return httpx.Response(200, json=completion())

    call_client(handle, openrouter_site_url="https://example.test", openrouter_site_name="Chatbot")


def test_length_finish_and_missing_usage_are_handled():
    result = call_client(
        lambda _: httpx.Response(
            200,
            json=completion(
                choices=[{"message": {"content": "답변"}, "finish_reason": "length"}],
                usage=None,
                model=None,
            ),
        )
    )
    assert result.truncated
    assert result.input_tokens is None
    assert result.model == "qwen/qwen3-30b-a3b-instruct-2507"


@pytest.mark.parametrize(
    "body",
    [
        {"choices": []},
        {"error": {"message": "private"}},
        completion(choices=[{"message": {"content": "  "}}]),
        completion(choices=[{"message": {"content": None}}]),
        completion(choices=[{"message": {"content": "private"}, "finish_reason": "error"}]),
        completion(usage={"prompt_tokens": -1}),
    ],
)
def test_invalid_response_is_a_safe_domain_error(body):
    with pytest.raises(AIClientError, match="AI_ERROR"):
        call_client(lambda _: httpx.Response(200, json=body))


def test_invalid_json_is_rejected():
    with pytest.raises(AIClientError):
        call_client(lambda _: httpx.Response(200, text="not-json"))


@pytest.mark.parametrize("key", [None, "", "   "])
def test_missing_key_never_calls_upstream(key):
    def handle(_):
        pytest.fail("키가 없으면 요청하면 안 된다")

    client = OpenRouterClient(
        Settings(openrouter_api_key=key), transport=httpx.MockTransport(handle)
    )
    with pytest.raises(AIClientError, match="AI_NOT_CONFIGURED"):
        asyncio.run(client.generate(MESSAGES))


@pytest.mark.parametrize("status", [400, 401, 402, 429, 500, 502, 503])
def test_http_errors_are_safe_and_not_retried(status, caplog):
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(status, json={"error": {"message": "private-provider-text"}})

    with pytest.raises(AIClientError, match="AI_ERROR"):
        call_client(handle)
    assert len(calls) == 1
    assert "private-provider-text" not in caplog.text
    assert "test-secret" not in caplog.text
    assert "ai_call_failed" in caplog.text


def test_total_timeout_applies_even_when_transport_has_no_timeout():
    async def handle(_):
        await asyncio.sleep(0.1)
        return httpx.Response(200, json=completion())

    with pytest.raises(AIClientError, match="AI_TIMEOUT"):
        call_client(handle, ai_timeout_seconds=0.01)


def test_httpx_timeout_is_mapped():
    def handle(request):
        raise httpx.ReadTimeout("private-transport-message", request=request)

    with pytest.raises(AIClientError, match="AI_TIMEOUT"):
        call_client(handle)


def test_network_failure_is_mapped():
    def handle(request):
        raise httpx.ConnectError("private-transport-message", request=request)

    with pytest.raises(AIClientError, match="AI_ERROR"):
        call_client(handle)


def test_success_logs_metadata_without_secret_or_content(caplog):
    caplog.set_level(logging.INFO)
    call_client(lambda _: httpx.Response(200, json=completion()))
    assert "ai_call_start" in caplog.text
    assert "ai_call_success" in caplog.text
    assert "provider=streamlake" in caplog.text
    assert "test-secret" not in caplog.text
    assert "질문" not in caplog.text
    assert "답변" not in caplog.text
