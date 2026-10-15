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
    assert 'src="https://cdn.jsdelivr.net/npm/marked@18.1.1/lib/marked.umd.js"' in response.text
    assert 'src="https://cdn.jsdelivr.net/npm/dompurify@3.4.17/dist/purify.min.js"' in response.text
    assert (
        'integrity="sha384-rATToyt6602Jnq8c7w8HZwmyOUgPL7mzxX01FBWoV48ns/EgkakGozpES+PnaYOI"'
        in response.text
    )
    assert (
        'integrity="sha384-P0JNneQf81HOl9VwNXK76cQ9VMD6Nfsnepxb0cCOg8+UzEdzgPHAPV4wVQrvYQSx"'
        in response.text
    )


@pytest.mark.parametrize(
    "path, content_type",
    [
        ("/static/css/common.css", "text/css"),
        ("/static/js/main.js", "text/javascript"),
        ("/static/js/api/api.js", "text/javascript"),
        ("/static/js/api/mock.js", "text/javascript"),
        ("/static/js/api/real.js", "text/javascript"),
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
