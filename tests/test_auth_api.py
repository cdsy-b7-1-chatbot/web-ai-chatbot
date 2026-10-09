import logging

import pytest
from sqlalchemy import select

from app.auth.security import decode_access_token, verify_password
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


# ── 로그인·로그아웃 ──

LOGIN = "/api/auth/login"
LOGOUT = "/api/auth/logout"


def _login(client, username="sangwoo", password="password123"):
    return client.post(LOGIN, json={"username": username, "password": password})


def test_login_returns_token_in_body_and_cookie(client, user, user_password):
    response = _login(client, password=user_password)

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert decode_access_token(body["access_token"]) == user.id
    assert response.cookies["access_token"] == body["access_token"]


def test_login_cookie_attributes(client, user, user_password):
    cookie = _login(client, password=user_password).headers["set-cookie"]

    assert "HttpOnly" in cookie
    assert "Secure" in cookie
    assert "SameSite=lax" in cookie
    assert "Path=/" in cookie
    assert "Max-Age=3600" in cookie  # JWT_EXPIRE_MINUTES 기본 60분과 같다


def test_login_cookie_follows_settings(client, user, user_password, configure):
    configure(cookie_secure="false", jwt_expire_minutes="5")

    cookie = _login(client, password=user_password).headers["set-cookie"]

    assert "Secure" not in cookie
    assert "Max-Age=300" in cookie


def test_login_ignores_username_case(client, user, user_password):
    assert _login(client, username="SangWoo", password=user_password).status_code == 200


@pytest.mark.parametrize(
    "username,password",
    [
        ("sangwoo", "wrong-password"),  # 틀린 비밀번호
        ("nobody", "password123"),  # 없는 아이디
        ("a!", "password123"),  # 가입 규칙에 안 맞는 아이디 — 422 가 아니라 같은 401
    ],
)
def test_login_failure_does_not_say_which_part_is_wrong(client, user, username, password):
    response = _login(client, username=username, password=password)

    assert response.status_code == 401
    assert response.json() == {
        "error": "INVALID_CREDENTIALS",
        "message": "아이디 또는 비밀번호가 올바르지 않습니다.",
    }
    assert "set-cookie" not in response.headers


def test_login_failure_log_has_reason_but_not_input(client, user, caplog):
    caplog.set_level(logging.INFO)

    _login(client, username="sangwoo", password="wrong-password")
    _login(client, username="password-typed-here", password="x")

    wrong, unknown = [m for m in caplog.messages if m.startswith("login_failed")]
    assert f"user_id={user.id} " in wrong
    assert "reason=wrong_password" in wrong
    assert "user_id=- " in unknown
    assert "reason=unknown_user" in unknown
    # 아이디 칸에 비밀번호를 잘못 친 경우에도 입력값이 로그에 남지 않는다
    assert "password-typed-here" not in caplog.text
    assert "wrong-password" not in caplog.text


def test_logout_deletes_cookie(client):
    response = client.post(LOGOUT)

    assert response.status_code == 204
    assert response.content == b""
    cookie = response.headers["set-cookie"]
    assert cookie.startswith('access_token="";')
    assert "Max-Age=0" in cookie
