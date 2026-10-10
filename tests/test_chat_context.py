from datetime import UTC, datetime

from app.chat.context import build_messages
from app.chat.repository import get_recent_chats
from app.db.models import Chat, Conversation, User


def test_latest_successful_pairs_are_selected_and_ordered(db, conversation):
    at = datetime(2026, 10, 9, tzinfo=UTC)
    for index in range(8):
        db.add(
            Chat(
                user_id=conversation.user_id,
                conversation_id=conversation.id,
                question=f"질문{index}",
                answer=f"답변{index}",
                status="success",
                created_at=at,
            )
        )
    db.add(
        Chat(
            user_id=conversation.user_id,
            conversation_id=conversation.id,
            question="실패 질문",
            status="failed",
            error_code="AI_TIMEOUT",
            created_at=at,
        )
    )
    db.commit()
    recent = get_recent_chats(db, conversation.id, 5)
    assert [row.question for row in recent] == [f"질문{i}" for i in range(3, 8)]
    messages = build_messages(recent, "마지막 질문")
    assert [m["role"] for m in messages] == ["system"] + ["user", "assistant"] * 5 + ["user"]
    assert messages[1]["content"] == "질문3"
    assert messages[-2]["content"] == "답변7"
    assert messages[-1]["content"] == "마지막 질문"


def test_other_rooms_and_users_are_not_context(db, conversation):
    other = User(username="someone", password_hash="hash")
    db.add(other)
    db.flush()
    for owner in (conversation.user_id, other.id):
        room = Conversation(user_id=owner, title="다른 방")
        db.add(room)
        db.flush()
        db.add(
            Chat(
                user_id=owner,
                conversation_id=room.id,
                question="private",
                answer="secret",
                status="success",
            )
        )
    db.commit()
    assert get_recent_chats(db, conversation.id, 5) == []
    assert len(build_messages([], "새 질문")) == 2


def test_failure_and_incomplete_pair_are_not_sent():
    chats = [
        Chat(question="실패", answer="오류", status="failed"),
        Chat(question="누락", answer=None, status="success"),
    ]
    assert len(build_messages(chats, "새 질문")) == 2
