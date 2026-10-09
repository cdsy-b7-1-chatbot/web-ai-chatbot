import logging
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import OptionalUser
from app.auth.security import create_access_token

ME = "/api/auth/me"


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_me_with_bearer_header(client, user, auth_headers):
    response = client.get(ME, headers=auth_headers)

    assert response.status_code == 200
    # password_hash·role 은 응답에 나가지 않는다
    assert response.json() == {"id": user.id, "username": "sangwoo"}


def test_me_with_cookie_after_login(client, user, user_password):
    client.post("/api/auth/login", json={"username": "sangwoo", "password": user_password})

    response = client.get(ME)  # 헤더 없이 쿠키만

    assert response.status_code == 200
    assert response.json()["id"] == user.id


def test_me_without_token_is_401(client):
    response = client.get(ME)

    assert response.status_code == 401
    assert response.json() == {"error": "UNAUTHORIZED", "message": "로그인이 필요합니다."}
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize(
    "make_token",
    [
        pytest.param(
            lambda user: create_access_token(user.id, now=datetime.now(UTC) - timedelta(hours=2)),
            id="expired",
        ),
        pytest.param(lambda user: create_access_token(user.id + 999), id="deleted-user"),
        pytest.param(lambda user: "not-a-jwt", id="garbage"),
    ],
)
def test_me_with_unusable_token_is_401(client, user, make_token):
    response = client.get(ME, headers=_bearer(make_token(user)))

    assert response.status_code == 401
    assert response.json()["error"] == "UNAUTHORIZED"


def test_header_wins_over_cookie(client, user, user_password):
    client.post("/api/auth/login", json={"username": "sangwoo", "password": user_password})

    # 쿠키는 유효해도 헤더를 먼저 본다 — 헤더 토큰이 틀리면 401
    assert client.get(ME, headers=_bearer("not-a-jwt")).status_code == 401


def test_non_bearer_header_falls_back_to_cookie(client, user, user_password):
    client.post("/api/auth/login", json={"username": "sangwoo", "password": user_password})

    assert client.get(ME, headers={"Authorization": "Basic abc"}).status_code == 200


def test_me_after_logout_is_401(client, user, user_password):
    client.post("/api/auth/login", json={"username": "sangwoo", "password": user_password})
    client.post("/api/auth/logout")

    assert client.get(ME).status_code == 401


@pytest.fixture
def optional_client(client):
    app = client.app

    @app.get("/test/optional")
    def optional_page(user: OptionalUser):
        return {"user_id": user.id if user else None}

    return TestClient(app, base_url="https://testserver")


def test_optional_user_is_none_without_login(optional_client):
    assert optional_client.get("/test/optional").json() == {"user_id": None}


def test_optional_user_with_login(optional_client, user, auth_headers):
    assert optional_client.get("/test/optional", headers=auth_headers).json() == {
        "user_id": user.id
    }


def test_optional_user_ignores_bad_token(optional_client):
    response = optional_client.get("/test/optional", headers=_bearer("not-a-jwt"))

    assert response.status_code == 200
    assert response.json() == {"user_id": None}


def test_docs_show_bearer_auth_on_protected_route(client):
    spec = client.get("/openapi.json").json()

    assert spec["components"]["securitySchemes"]["HTTPBearer"]["scheme"] == "bearer"
    assert spec["paths"][ME]["get"]["security"] == [{"HTTPBearer": []}]
    assert "401" in spec["paths"][ME]["get"]["responses"]


def test_request_logs_carry_token_owner_user_id(client, user, auth_headers, caplog):
    caplog.set_level(logging.INFO)

    client.get(ME, headers=auth_headers)

    received = next(m for m in caplog.messages if m.startswith("request_received"))
    completed = next(m for m in caplog.messages if m.startswith("request_completed"))
    assert f"user_id={user.id} " in received
    assert f"user_id={user.id} " in completed


def test_request_logs_without_valid_token_have_no_user_id(client, caplog):
    caplog.set_level(logging.INFO)

    client.get(ME, headers=_bearer("not-a-jwt"))

    received = next(m for m in caplog.messages if m.startswith("request_received"))
    assert "user_id=- " in received
