import pytest
from fastapi.testclient import TestClient

from app.main import create_app

FRONTEND = "https://fe.onrender.com"


def _preflight(client, origin):
    return client.options(
        "/api/auth/login",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )


def test_no_cors_headers_by_default():
    response = TestClient(create_app()).get("/api/health", headers={"Origin": FRONTEND})

    assert "access-control-allow-origin" not in response.headers


@pytest.fixture
def cors_client(configure):
    configure(cors_origins=f"{FRONTEND}, https://other.example.com")
    return TestClient(create_app())


def test_preflight_from_allowed_origin(cors_client):
    response = _preflight(cors_client, FRONTEND)

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == FRONTEND
    assert "authorization" in response.headers["access-control-allow-headers"].lower()
    # 토큰은 헤더로 보내므로 쿠키 전송은 허용하지 않는다
    assert "access-control-allow-credentials" not in response.headers


def test_preflight_from_unknown_origin_is_rejected(cors_client):
    response = _preflight(cors_client, "https://evil.example.com")

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_second_origin_in_list_is_allowed(cors_client):
    response = _preflight(cors_client, "https://other.example.com")

    assert response.headers["access-control-allow-origin"] == "https://other.example.com"


def test_frontend_can_read_request_id(cors_client):
    response = cors_client.get("/api/health", headers={"Origin": FRONTEND})

    assert response.headers["access-control-allow-origin"] == FRONTEND
    assert "x-request-id" in response.headers["access-control-expose-headers"].lower()


def test_server_error_still_has_cors_headers(configure):
    # CORS 가 바깥쪽 미들웨어라 500 응답에도 헤더가 붙는다 — 안 붙으면 브라우저가 오류 내용을 가린다
    configure(cors_origins=FRONTEND)
    app = create_app()

    @app.get("/test/boom")
    def boom():
        raise RuntimeError("boom")

    response = TestClient(app).get("/test/boom", headers={"Origin": FRONTEND})

    assert response.status_code == 500
    assert response.headers["access-control-allow-origin"] == FRONTEND
