"""로그인 사용자 확인 — 라우트에서 `user: CurrentUser` 로 받는다. 설계: #1 3장·4장.

    @router.get("/api/me/chats")
    def my_chats(user: CurrentUser, db: SessionDep): ...   # 비로그인이면 401 UNAUTHORIZED

    @router.get("/")
    def page(user: OptionalUser): ...                      # 비로그인이면 None (화면 분기용)

토큰은 `Authorization: Bearer` 헤더를 먼저 보고, 없으면 쿠키를 본다.
사용자는 매 요청 DB 에서 다시 읽는다 — 탈퇴·역할 변경이 토큰 만료를 기다리지 않고 바로 반영된다.
"""

from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.requests import HTTPConnection

from app.auth.repository import get_user
from app.auth.security import ACCESS_TOKEN_COOKIE, decode_access_token
from app.core.errors import AppError, ErrorCode
from app.db.database import SessionDep
from app.db.models import User

UNAUTHORIZED_MESSAGE = "로그인이 필요합니다."

# /docs 의 Authorize 버튼과 자물쇠 표시용. 쿠키도 봐야 해서 실제로 읽는 건 token_from_request 다
_bearer_scheme = HTTPBearer(
    auto_error=False, description="로그인 응답의 `access_token` 을 붙여 넣는다"
)


def token_from_request(conn: HTTPConnection) -> str | None:
    """`Authorization: Bearer <토큰>` 헤더 → 없으면 쿠키. 요청 미들웨어도 이 함수로 읽는다."""
    scheme, _, token = conn.headers.get("authorization", "").partition(" ")
    if scheme.lower() == "bearer" and token.strip():
        return token.strip()
    return conn.cookies.get(ACCESS_TOKEN_COOKIE) or None


def get_current_user_optional(
    request: Request,
    db: SessionDep,
    _: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
) -> User | None:
    """로그인했으면 User, 아니면 None — 토큰 없음·만료·위조·없는 사용자를 모두 비로그인으로 본다."""
    token = token_from_request(request)
    user_id = decode_access_token(token) if token else None
    return get_user(db, user_id) if user_id is not None else None


def get_current_user(user: Annotated[User | None, Depends(get_current_user_optional)]) -> User:
    """비로그인이면 401 UNAUTHORIZED — 프론트는 로그인 화면으로 보낸다."""
    if user is None:
        raise AppError(
            401,
            ErrorCode.UNAUTHORIZED,
            UNAUTHORIZED_MESSAGE,
            headers={"WWW-Authenticate": "Bearer"},  # 401 응답에는 인증 방식을 알린다(RFC 9110)
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[User | None, Depends(get_current_user_optional)]
