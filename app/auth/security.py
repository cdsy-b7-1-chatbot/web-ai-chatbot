"""비밀번호 해싱과 로그인 토큰(JWT) 발급·검증. HTTP·DB 를 모르는 함수만 둔다. 설계: #1 1장·3장."""

from datetime import UTC, datetime, timedelta
from functools import lru_cache

import jwt
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

from app.core.config import get_settings

JWT_ALGORITHM = "HS256"
# HS256 키는 해시 출력(32바이트) 이상이어야 한다(RFC 7518 3.2). 짧으면 무차별 대입으로 키를 찾을 수 있다
JWT_SECRET_MIN_BYTES = 32

JWT_SECRET_MESSAGE = (
    f"JWT_SECRET 이 없거나 너무 짧습니다({JWT_SECRET_MIN_BYTES}바이트 이상). "
    "로컬은 .env.example 을 .env 로 복사하고, 배포는 Render 환경 변수에 넣으세요. "
    ' 새 값 만들기: uv run python -c "import secrets; print(secrets.token_urlsafe(32))"'
)

# Argon2id OWASP 최소 권장값(메모리 19MiB·반복 2·병렬 1). 라이브러리 기본값(64MiB·3·4)은
# Render 무료 인스턴스(RAM 512MB·CPU 0.1)에 무겁다
_password_hash = PasswordHash((Argon2Hasher(memory_cost=19 * 1024, time_cost=2, parallelism=1),))


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


@lru_cache
def _dummy_hash() -> str:
    return hash_password("dummy-password-for-timing")


def verify_password(password: str, password_hash: str | None) -> bool:
    """`password_hash` 가 None(없는 아이디)이어도 같은 시간만큼 검증하고 False 를 돌려준다.

    없는 아이디일 때 바로 돌아가면 응답이 빨라져서, 응답 시간으로 가입된 아이디를 알아낼 수 있다.
    """
    if password_hash is None:
        _password_hash.verify(password, _dummy_hash())
        return False
    return _password_hash.verify(password, password_hash)


def _signing_key() -> str:
    secret = get_settings().jwt_secret
    if secret is None or len(secret.encode()) < JWT_SECRET_MIN_BYTES:
        raise RuntimeError(JWT_SECRET_MESSAGE)
    return secret


def ensure_jwt_secret() -> None:
    """앱 시작 시 호출 — 서명 키가 없거나 짧으면 첫 로그인 때가 아니라 시작할 때 멈춘다."""
    _signing_key()


def create_access_token(user_id: int, *, now: datetime | None = None) -> str:
    """`sub` 에 user_id 만 넣는다 — role 은 넣지 않는다(매 요청 DB 에서 읽어 변경이 바로 반영되게)."""
    issued_at = now or datetime.now(UTC)
    payload = {
        "sub": str(user_id),  # JWT 규격상 문자열이어야 한다(pyjwt 가 숫자를 거부)
        "iat": issued_at,
        "exp": issued_at + timedelta(minutes=get_settings().jwt_expire_minutes),
    }
    return jwt.encode(payload, _signing_key(), algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> int | None:
    """서명과 만료가 맞으면 user_id, 아니면 None. 실패 이유는 나누지 않는다(응답은 모두 401)."""
    try:
        payload = jwt.decode(
            token,
            _signing_key(),
            # 허용 알고리즘을 고정한다 — 토큰 헤더의 alg 를 믿으면 서명 없는 "none" 토큰이 통과할 수 있다
            algorithms=[JWT_ALGORITHM],
            options={"require": ["sub", "exp"]},
        )
        return int(payload["sub"])
    except (jwt.InvalidTokenError, ValueError):
        return None
