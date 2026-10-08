"""회원가입 로직. HTTP(쿠키·헤더)는 router 가 맡는다."""

import logging

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import repository
from app.auth.security import hash_password
from app.core.errors import AppError, ErrorCode
from app.core.logging import log_event
from app.db.models import User

logger = logging.getLogger(__name__)

USERNAME_TAKEN_MESSAGE = "이미 사용 중인 아이디입니다."


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
