import logging

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from app.core.errors import AppError, ErrorCode
from app.main import create_app


class _SignupLike(BaseModel):
    username: str = Field(min_length=3)
    password: str = Field(min_length=8)


@pytest.fixture
def client():
    app = create_app()

    @app.get("/test/app-error")
    def raise_app_error():
        raise AppError(403, ErrorCode.FORBIDDEN, "관리자만 볼 수 있습니다.")

    @app.post("/test/validate")
    def validate(body: _SignupLike):
        return {"ok": True}

    return TestClient(app)


def test_app_error_uses_its_own_status_and_code(client):
    response = client.get("/test/app-error")

    assert response.status_code == 403
    assert response.json() == {"error": "FORBIDDEN", "message": "관리자만 볼 수 있습니다."}


def test_unknown_path_is_converted_from_fastapi_default(client):
    response = client.get("/api/does-not-exist")

    assert response.status_code == 404
    assert response.json() == {"error": "NOT_FOUND", "message": "요청한 경로를 찾을 수 없습니다."}


def test_wrong_method_keeps_allow_header(client):
    response = client.post("/api/health")

    assert response.status_code == 405
    assert response.json()["error"] == "METHOD_NOT_ALLOWED"
    assert response.headers["allow"] == "GET"


def test_validation_error_hides_details_from_response(client):
    response = client.post("/test/validate", json={"username": "ab", "password": "short-pw"})

    assert response.status_code == 422
    assert response.json() == {"error": "VALIDATION_ERROR", "message": "입력값이 올바르지 않습니다."}


def test_validation_error_logs_field_but_not_input_value(client, caplog):
    caplog.set_level(logging.INFO)

    client.post("/test/validate", json={"username": "ab", "password": "pw123"})

    [message] = [m for m in caplog.messages if m.startswith("validation_failed")]
    assert "body.username:string_too_short" in message
    assert "body.password:string_too_short" in message
    assert "pw123" not in message
