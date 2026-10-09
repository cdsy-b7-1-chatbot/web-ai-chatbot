from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.auth.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.core.config import get_settings


def test_password_is_stored_as_argon2id_hash_with_owasp_parameters():
    password_hash = hash_password("password123")

    assert password_hash.startswith("$argon2id$v=19$m=19456,t=2,p=1$")
    assert "password123" not in password_hash


def test_same_password_gets_different_hash():
    # 솔트가 매번 달라서, 해시가 같으면 비밀번호가 같다는 것을 알 수 없다
    assert hash_password("password123") != hash_password("password123")


def test_verify_password():
    password_hash = hash_password("비밀번호는한글도됩니다")

    assert verify_password("비밀번호는한글도됩니다", password_hash) is True
    assert verify_password("wrong-password", password_hash) is False


def test_verify_password_without_user_is_false():
    assert verify_password("password123", None) is False


def test_token_round_trip():
    assert decode_access_token(create_access_token(42)) == 42


def test_token_holds_only_user_id_and_times():
    payload = jwt.decode(create_access_token(42), options={"verify_signature": False})

    assert set(payload) == {"sub", "iat", "exp"}
    assert payload["sub"] == "42"


def test_token_expires_after_configured_minutes(configure):
    configure(jwt_expire_minutes="5")
    issued = datetime.now(UTC) - timedelta(minutes=6)

    assert decode_access_token(create_access_token(42, now=issued)) is None


def test_token_is_valid_before_expiry(configure):
    configure(jwt_expire_minutes="5")
    issued = datetime.now(UTC) - timedelta(minutes=4)

    assert decode_access_token(create_access_token(42, now=issued)) == 42


def test_token_signed_with_other_key_is_rejected():
    forged = jwt.encode({"sub": "42", "exp": datetime.now(UTC) + timedelta(hours=1)}, "x" * 32)

    assert decode_access_token(forged) is None


def test_unsigned_none_algorithm_token_is_rejected():
    forged = jwt.encode(
        {"sub": "42", "exp": datetime.now(UTC) + timedelta(hours=1)}, None, algorithm="none"
    )

    assert decode_access_token(forged) is None


def test_tampered_token_is_rejected():
    header, payload, signature = create_access_token(42).split(".")
    other_payload = create_access_token(1).split(".")[1]

    assert decode_access_token(f"{header}.{other_payload}.{signature}") is None


@pytest.mark.parametrize("token", ["", "not-a-jwt", "a.b.c"])
def test_garbage_token_is_rejected(token):
    assert decode_access_token(token) is None


def test_token_without_expiry_is_rejected():
    no_exp = jwt.encode({"sub": "42"}, get_settings().jwt_secret, algorithm="HS256")

    assert decode_access_token(no_exp) is None
