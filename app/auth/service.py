"""회원가입·로그인 로직. HTTP(쿠키·헤더)는 router 가 맡는다."""

import logging

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import repository
from app.auth.security import create_access_token, hash_password, verify_password
from app.core.errors import AppError, ErrorCode
from app.core.logging import log_event
from app.db.models import User

logger = logging.getLogger(__name__)

USERNAME_TAKEN_MESSAGE = "이미 사용 중인 아이디입니다."
INVALID_CREDENTIALS_MESSAGE = "아이디 또는 비밀번호가 올바르지 않습니다."


def signup(db: Session, username: str, password: str) -> User:
    """`username` 은 schemas 에서 이미 소문자로 바뀌어 들어온다."""
    try:
        user = repository.create_user(db, username=username, password_hash=hash_password(password))
    except IntegrityError:
        # 먼저 조회하고 저장하면 그 사이에 같은 아이디로 동시에 가입할 수 있다 — UNIQUE 위반으로 판단한다
        db.rollback()
        if repository.get_user_by_username(db, username) is None:
            raise  # UNIQUE 가 아닌 다른 제약 위반 — 처리하지 않은 오류(500)로 둔다
        log_event(logger, "signup_failed", reason="username_taken", username=username)
        raise AppError(409, ErrorCode.USERNAME_TAKEN, USERNAME_TAKEN_MESSAGE) from None
    log_event(logger, "signup_succeeded", user_id=user.id, username=username)
    return user


def login(db: Session, username: str, password: str) -> str:
    """맞으면 access token. 없는 아이디와 틀린 비밀번호는 같은 응답이다(가입 여부를 알려주지 않음)."""
    user = repository.get_user_by_username(db, username)
    # 없는 아이디여도 verify_password 를 먼저 부른다(응답 시간을 같게 — security.verify_password)
    if not verify_password(password, user.password_hash if user else None) or user is None:
        # 입력한 아이디는 남기지 않는다 — 아이디 칸에 비밀번호를 잘못 치면 로그에 비밀번호가 남는다
        reason = "unknown_user" if user is None else "wrong_password"
        log_event(
            logger,
            "login_failed",
            logging.WARNING,
            reason=reason,
            user_id=user.id if user else None,
        )
        raise AppError(401, ErrorCode.INVALID_CREDENTIALS, INVALID_CREDENTIALS_MESSAGE)
    log_event(logger, "login_succeeded", user_id=user.id)
    return create_access_token(user.id)
