"""기록 조회 계약은 이슈 #1을 따른다. 실패 이력도 함께 조회한다."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Chat


def list_chats(
    db: Session,
    user_id: int,
    limit: int = 50,
    offset: int = 0,
    *,
    conversation_id: int | None = None,
) -> list[Chat]:
    query = select(Chat).where(Chat.user_id == user_id)
    if conversation_id is not None:
        query = query.where(Chat.conversation_id == conversation_id)
    return list(
        db.scalars(
            query.order_by(Chat.created_at.desc(), Chat.id.desc()).limit(limit).offset(offset)
        )
    )
