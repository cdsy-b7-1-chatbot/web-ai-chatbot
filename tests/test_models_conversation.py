import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from app.db.models import Conversation


def test_new_conversation_gets_timestamps(db, conversation):
    db.refresh(conversation)

    assert conversation.created_at is not None
    assert conversation.updated_at is not None


def test_conversation_needs_existing_user(db):
    db.add(Conversation(user_id=999, title="주인 없는 방"))

    with pytest.raises(IntegrityError):
        db.commit()


def test_index_for_conversation_list_exists(engine):
    indexes = {
        ix["name"]: ix["column_names"] for ix in inspect(engine).get_indexes("conversations")
    }

    assert indexes["ix_conversations_user_id_updated_at"] == ["user_id", "updated_at"]
