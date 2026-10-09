from unittest.mock import Mock

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.chat import repository
from app.db.models import Conversation, User


def test_created_conversation_is_committed(engine, db, user):
    room = repository.create_conversation(db, user.id, "배포 방법")
    with Session(engine) as reader:
        saved = reader.get(Conversation, room.id)
        assert saved.title == "배포 방법"
        assert saved.user_id == user.id


def test_get_conversation_checks_ownership(db, user, conversation):
    other = User(username="other", password_hash="hash")
    db.add(other)
    db.commit()
    assert repository.get_conversation(db, conversation.id, user.id).id == conversation.id
    assert repository.get_conversation(db, conversation.id, other.id) is None
    assert repository.get_conversation(db, 99999, user.id) is None


def test_create_failure_rolls_back_and_hides_exception_text(caplog):
    db = Mock(spec=Session)
    db.commit.side_effect = SQLAlchemyError("private-password-secret")
    with pytest.raises(SQLAlchemyError):
        repository.create_conversation(db, 1, "private-question")
    db.rollback.assert_called_once()
    assert "db_save_failed" in caplog.text
    assert "private-password-secret" not in caplog.text
    assert "private-question" not in caplog.text
