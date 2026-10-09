"""users 저장·조회."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import User


def get_user(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def get_user_by_username(db: Session, username: str) -> User | None:
    return db.scalar(select(User).where(User.username == username))


def create_user(db: Session, *, username: str, password_hash: str) -> User:
    """같은 username 이 이미 있으면 커밋에서 IntegrityError(UNIQUE) — 호출하는 쪽이 처리한다."""
    user = User(username=username, password_hash=password_hash)
    db.add(user)
    db.commit()
    return user
