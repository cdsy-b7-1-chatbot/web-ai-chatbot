import logging
import re

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.errors import register_exception_handlers
from app.core.logging import log_event
from app.core.middleware import RequestContextMiddleware
from app.main import create_app


def _field(message: str, key: str) -> str:
    return re.search(rf"\b{key}=(\S+)", message).group(1)


def _events(caplog, name: str) -> list[str]:
    return [m for m in caplog.messages if m.startswith(f"{name} ")]


@pytest.fixture
def client():
    return TestClient(create_app())


def test_response_carries_server_generated_request_id(client):
    response = client.get("/api/health", headers={"X-Request-ID": "forged"})

    request_id = response.headers["x-request-id"]
    assert re.fullmatch(r"[0-9a-f]{12}", request_id)


def test_each_request_gets_a_new_request_id(client):
    first = client.get("/api/health").headers["x-request-id"]
    second = client.get("/api/health").headers["x-request-id"]

    assert first != second


def test_logs_start_and_end_with_same_request_id(client, caplog):
    caplog.set_level(logging.INFO)

    response = client.get("/")

    [received] = _events(caplog, "request_received")
    [completed] = _events(caplog, "request_completed")
    request_id = response.headers["x-request-id"]
    assert _field(received, "request_id") == request_id
    assert _field(completed, "request_id") == request_id
    assert "method=GET path=/ " in f"{received} "
    assert "status=200" in completed
    assert re.search(r"duration_ms=\d+", completed)


def test_completed_log_records_error_status(client, caplog):
    caplog.set_level(logging.INFO)

    client.get("/api/does-not-exist")

    [completed] = _events(caplog, "request_completed")
    assert "status=404" in completed


def _records(caplog, name: str) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.getMessage().startswith(f"{name} ")]


QUIET_PATHS = ["/static/css/common.css", "/api/health"]


@pytest.mark.parametrize("path", QUIET_PATHS)
def test_quiet_path_requests_are_hidden_at_info(client, caplog, path):
    caplog.set_level(logging.INFO)

    response = client.get(path)

    assert response.status_code == 200
    assert response.headers["x-request-id"]  # 로그 레벨만 낮출 뿐 request_id 는 그대로 붙는다
    assert _events(caplog, "request_received") == []
    assert _events(caplog, "request_completed") == []


@pytest.mark.parametrize("path", QUIET_PATHS)
def test_quiet_path_requests_are_logged_at_debug(client, caplog, path):
    caplog.set_level(logging.DEBUG)

    client.get(path)

    [received] = _records(caplog, "request_received")
    [completed] = _records(caplog, "request_completed")
    assert received.levelno == completed.levelno == logging.DEBUG
    assert f"path={path}" in received.getMessage()


def test_failed_static_file_request_is_logged_at_info_with_path(client, caplog):
    caplog.set_level(logging.INFO)

    client.get("/static/js/missing.js")

    assert _events(caplog, "request_received") == []
    [completed] = _events(caplog, "request_completed")
    assert "status=404" in completed
    assert "path=/static/js/missing.js" in completed


@pytest.mark.parametrize("path", ["/", "/api/auth/me", "/staticfoo"])
def test_other_requests_stay_at_info(client, caplog, path):
    caplog.set_level(logging.INFO)

    client.get(path)

    [received] = _events(caplog, "request_received")
    [completed] = _events(caplog, "request_completed")
    assert f"path={path} " in f"{received} "
    assert "path=" not in completed  # 일반 요청의 끝 로그 형식은 그대로


@pytest.fixture
def app_with_user():
    """토큰에서 user_id=7 을 꺼냈다고 가정한 앱 — 인증 기능이 붙은 뒤의 모습."""
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware, resolve_user_id=lambda conn: 7)
    register_exception_handlers(app)
    endpoint_logger = logging.getLogger("test.endpoint")

    @app.get("/sync")
    def sync_endpoint():
        log_event(endpoint_logger, "inside_sync")
        return {}

    @app.get("/async")
    async def async_endpoint():
        log_event(endpoint_logger, "inside_async")
        return {}

    @app.get("/boom")
    def boom():
        raise RuntimeError("db exploded\nINFO login_success user_id=1")

    return app


@pytest.mark.parametrize(("path", "event"), [("/sync", "inside_sync"), ("/async", "inside_async")])
def test_request_context_reaches_endpoint_logs(app_with_user, caplog, path, event):
    caplog.set_level(logging.INFO)

    response = TestClient(app_with_user).get(path)

    [message] = _events(caplog, event)
    assert _field(message, "request_id") == response.headers["x-request-id"]
    assert _field(message, "user_id") == "7"


def test_unhandled_error_becomes_500_json_with_request_id(app_with_user, caplog):
    caplog.set_level(logging.INFO)

    response = TestClient(app_with_user).get("/boom")

    assert response.status_code == 500
    assert response.json() == {
        "error": "INTERNAL_ERROR",
        "message": "서버 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.",
    }
    assert "db exploded" not in response.text
    [error] = _events(caplog, "unhandled_error")
    assert _field(error, "request_id") == response.headers["x-request-id"]
    assert "error_type=RuntimeError" in error
    assert "\n" not in error  # 스택 트레이스·예외 메시지도 한 줄 안에
    assert "db exploded" in error
    [completed] = _events(caplog, "request_completed")
    assert "status=500" in completed
