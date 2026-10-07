import pytest
from sqlalchemy.exc import DataError, IntegrityError

from app.db.models import User
from app.db.models.user import USERNAME_MAX_LENGTH


def test_new_user_gets_default_role_and_created_at(db, user):
    db.refresh(user)

    assert user.role == "user"
    assert user.created_at is not None


def test_username_must_be_unique(db, user):
    db.add(User(username="sangwoo", password_hash="other"))

    with pytest.raises(IntegrityError):
        db.commit()


def test_role_outside_allowed_values_is_rejected(db):
    db.add(User(username="mallory", password_hash="h", role="root"))

    with pytest.raises(IntegrityError):
        db.commit()


@pytest.mark.postgres
def test_username_longer_than_limit_is_rejected(db):
    # SQLite 는 길이를 검사하지 않아 그대로 저장된다 — 가입 API 는 DB 에 닿기 전에 길이를 막아야 한다(422)
    db.add(User(username="a" * (USERNAME_MAX_LENGTH + 1), password_hash="h"))

    with pytest.raises(DataError):
        db.commit()


@pytest.mark.postgres
def test_created_at_keeps_timezone(db, user):
    # SQLite 는 시간대를 버리고 돌려준다 — 응답의 시각 형식이 배포(Postgres)와 달라진다
    db.refresh(user)

    assert user.created_at.tzinfo is not None
