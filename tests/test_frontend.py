"""프론트엔드 정적 파일 제공과 ES Module 연결을 검증한다."""

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

FRONTEND_DIRECTORY = Path(__file__).resolve().parents[1] / "frontend"
MODULE_IMPORT_PATTERN = re.compile(r'from\s+["\'](?P<path>\.[^"\']+)["\']')


@pytest.fixture
def frontend_client() -> TestClient:
    return TestClient(create_app())


def test_frontend_entrypoint_is_served(frontend_client: TestClient) -> None:
    response = frontend_client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert 'src="/static/js/main.js"' in response.text
    assert 'data-auth-api-mode="mock"' not in response.text
    assert 'data-chat-api-mode="mock"' not in response.text
    assert 'data-health-api-mode="mock"' not in response.text
    assert 'get("apiMode") === "mock"' in response.text
    assert (
        'name="description" content="질문하고, 이해하고, 정리하는 나만의 AI 챗봇"' in response.text
    )
    assert 'property="og:title" content="Web AI Chatbot"' in response.text
    assert (
        'property="og:description" content="질문하고, 이해하고, 정리하는 나만의 AI 챗봇"'
        in response.text
    )
    assert 'rel="icon" href="/static/favicon.svg" type="image/svg+xml"' in response.text


@pytest.mark.parametrize(
    "path, content_type",
    [
        ("/static/css/common.css", "text/css"),
        ("/static/js/main.js", "text/javascript"),
        ("/static/js/api/api.js", "text/javascript"),
        ("/static/js/api/mock.js", "text/javascript"),
        ("/static/js/api/real.js", "text/javascript"),
        ("/static/favicon.svg", "image/svg+xml"),
    ],
)
def test_frontend_static_assets_are_served(
    frontend_client: TestClient, path: str, content_type: str
) -> None:
    response = frontend_client.get(path)

    assert response.status_code == 200
    assert content_type in response.headers["content-type"]


def test_javascript_module_import_paths_exist() -> None:
    for module_path in FRONTEND_DIRECTORY.glob("js/**/*.js"):
        for match in MODULE_IMPORT_PATTERN.finditer(module_path.read_text(encoding="utf-8")):
            imported_path = (module_path.parent / match.group("path")).resolve()
            assert imported_path.is_file(), (
                f"{module_path}의 import 경로가 없습니다: {match.group('path')}"
            )
