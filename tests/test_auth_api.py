import logging

import pytest
from sqlalchemy import select

from app.auth.security import verify_password
from app.db.models import User

SIGNUP = "/api/auth/signup"


def _signup(client, username="sangwoo", password="password123"):
    return client.post(SIGNUP, json={"username": username, "password": password})


# ── 회원가입 ──


def test_signup_returns_created_user(client):
    response = _signup(client)

    assert response.status_code == 201
    body = response.json()
    assert body == {"id": body["id"], "username": "sangwoo"}


def test_signup_stores_password_as_hash(client, db):
    _signup(client, password="password123")

    stored = db.scalar(select(User).where(User.username == "sangwoo"))
    assert stored.password_hash != "password123"
    assert verify_password("password123", stored.password_hash)


def test_signup_lowercases_username(client):
    response = _signup(client, username="SangWoo")

    assert response.json()["username"] == "sangwoo"


@pytest.mark.parametrize("taken", ["sangwoo", "SANGWOO"])
def test_signup_rejects_taken_username_ignoring_case(client, user, taken):
    response = _signup(client, username=taken)

    assert response.status_code == 409
    assert response.json() == {"error": "USERNAME_TAKEN", "message": "이미 사용 중인 아이디입니다."}


def test_signup_ignores_role_in_request(client, db):
    response = client.post(
        SIGNUP, json={"username": "mallory", "password": "password123", "role": "admin"}
    )

    assert response.status_code == 201
    assert db.get(User, response.json()["id"]).role == "user"


@pytest.mark.parametrize(
    "username",
    [
        "ab",  # 3자 미만
        "a" * 21,  # 20자 초과 — 막지 않으면 Postgres varchar(20) 에서 500
        "sang woo",
        "sang-woo",
        "상우abc",
        "sangwoo\n",  # 끝 줄바꿈 — 정규식 $ 가 줄바꿈 앞에서 멈추는 엔진도 있다
    ],
)
def test_signup_rejects_invalid_username(client, username):
    response = _signup(client, username=username)

    assert response.status_code == 422
    assert response.json()["error"] == "VALIDATION_ERROR"


@pytest.mark.parametrize("password", ["a" * 7, "a" * 65])
def test_signup_rejects_password_out_of_range(client, password):
    assert _signup(client, password=password).status_code == 422


@pytest.mark.parametrize("username,password", [("abc", "a" * 8), ("a" * 20, "가" * 64)])
def test_signup_accepts_boundary_lengths(client, username, password):
    assert _signup(client, username=username, password=password).status_code == 201


def test_signup_logs_without_password(client, caplog):
    caplog.set_level(logging.INFO)

    _signup(client, password="secret-pw-123")

    [message] = [m for m in caplog.messages if m.startswith("signup_succeeded")]
    assert "username=sangwoo" in message
    assert "secret-pw-123" not in caplog.text
