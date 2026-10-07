import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from app.db.models import Chat


def _chat(conversation, **fields):
    values = {
        "user_id": conversation.user_id,
        "conversation_id": conversation.id,
        "question": "배포는 어떻게 해?",
        "status": "success",
    } | fields
    return Chat(**values)


def test_successful_chat_with_usage_is_saved(db, conversation):
    chat = _chat(
        conversation,
        answer="Render 에서 …",
        model="claude-haiku-4-5",
        input_tokens=120,
        output_tokens=80,
        latency_ms=1240,
    )
    db.add(chat)
    db.commit()
    db.refresh(chat)

    assert chat.created_at is not None
    assert chat.input_tokens == 120


def test_failed_chat_can_omit_answer_and_usage(db, conversation):
    db.add(_chat(conversation, status="failed", error_code="AI_TIMEOUT", latency_ms=10012))
    db.commit()

    saved = db.query(Chat).one()
    assert saved.answer is None
    assert saved.input_tokens is None
    assert saved.error_code == "AI_TIMEOUT"


def test_status_outside_allowed_values_is_rejected(db, conversation):
    db.add(_chat(conversation, status="pending"))

    with pytest.raises(IntegrityError):
        db.commit()


@pytest.mark.parametrize("field", ["conversation_id", "user_id"])
def test_chat_needs_existing_conversation_and_user(db, conversation, field):
    db.add(_chat(conversation, **{field: 999}))

    with pytest.raises(IntegrityError):
        db.commit()


def test_indexes_for_context_and_user_logs_exist(engine):
    indexes = {ix["name"]: ix["column_names"] for ix in inspect(engine).get_indexes("chats")}

    assert indexes["ix_chats_conversation_id_created_at"] == ["conversation_id", "created_at"]
    assert indexes["ix_chats_user_id_created_at"] == ["user_id", "created_at"]


def test_init_db_creates_exactly_the_three_tables(engine):
    assert set(inspect(engine).get_table_names()) == {"users", "conversations", "chats"}
