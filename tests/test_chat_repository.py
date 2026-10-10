from datetime import UTC, datetime
from unittest.mock import Mock

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.chat import repository
from app.db.models import Chat, Conversation, User


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


def test_save_chat_uses_room_owner_and_updates_time(engine, db, conversation, caplog):
    import logging

    caplog.set_level(logging.INFO)
    conversation.updated_at = datetime(2000, 1, 1, tzinfo=UTC)
    db.commit()
    saved = repository.save_chat(
        db,
        conversation=conversation,
        question="질문",
        answer="답변",
        status="success",
        model="qwen/test",
        input_tokens=10,
        output_tokens=20,
        latency_ms=12,
    )
    with Session(engine) as reader:
        row = reader.get(Chat, saved.id)
        room = reader.get(Conversation, conversation.id)
        assert row.user_id == conversation.user_id
        assert (row.question, row.answer, row.input_tokens, row.output_tokens) == (
            "질문",
            "답변",
            10,
            20,
        )
        assert room.updated_at.year > 2000
    assert "db_save_success" in caplog.text


def test_failed_chat_keeps_question_and_omits_usage(db, conversation):
    saved = repository.save_chat(
        db,
        conversation=conversation,
        question="질문",
        answer=None,
        status="failed",
        error_code="AI_TIMEOUT",
        model="qwen/test",
        latency_ms=30000,
    )
    assert saved.answer is None
    assert saved.input_tokens is None
    assert saved.error_code == "AI_TIMEOUT"


def test_save_failure_rolls_back_room_update_and_session_remains_usable(db, conversation):
    old_time = datetime(2000, 1, 1, tzinfo=UTC)
    conversation.updated_at = old_time
    db.commit()
    with pytest.raises(IntegrityError):
        repository.save_chat(
            db, conversation=conversation, question="질문", answer="답변", status="invalid"
        )
    assert list(db.scalars(select(Chat))) == []
    db.refresh(conversation)
    assert conversation.updated_at.year == 2000
    assert (
        repository.save_chat(
            db, conversation=conversation, question="재시도", answer="답변", status="success"
        ).id
        is not None
    )


@pytest.mark.parametrize("operation", ["create", "save"])
def test_refresh_failure_occurs_before_commit_and_rolls_back(db, user, monkeypatch, operation):
    room = repository.create_conversation(db, user.id, "기존 방")
    room.updated_at = datetime(2000, 1, 1, tzinfo=UTC)
    db.commit()
    room_id = room.id

    def fail_refresh(*args, **kwargs):
        raise SQLAlchemyError("private-refresh-error")

    with monkeypatch.context() as patch:
        patch.setattr(db, "refresh", fail_refresh)
        with pytest.raises(SQLAlchemyError):
            if operation == "create":
                repository.create_conversation(db, user.id, "저장되면 안 되는 방")
            else:
                repository.save_chat(
                    db, conversation=room, question="질문", answer="답변", status="success"
                )
    assert len(list(db.scalars(select(Conversation)))) == 1
    assert list(db.scalars(select(Chat))) == []
    db.refresh(db.get(Conversation, room_id))
    assert db.get(Conversation, room_id).updated_at.year == 2000
