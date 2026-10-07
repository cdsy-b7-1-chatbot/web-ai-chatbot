import pytest
from sqlalchemy.exc import IntegrityError

from app.db.models import User


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
