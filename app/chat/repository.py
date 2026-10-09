"""대화방·대화 저장과 조회. HTTP 오류 변환은 service가 담당한다."""

import logging
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.logging import log_event
from app.db.models import Chat, Conversation

logger = logging.getLogger(__name__)


def create_conversation(db: Session, user_id: int, title: str) -> Conversation:
    conversation = Conversation(user_id=user_id, title=title)
    try:
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
    except SQLAlchemyError as exc:
        db.rollback()
        # DB 예외 원문에는 접속 정보와 질문이 포함될 수 있어 종류만 남긴다.
        log_event(
            logger,
            "db_save_failed",
            logging.ERROR,
            operation="create_conversation",
            error_type=type(exc).__name__,
        )
        raise
    log_event(logger, "conversation_created", conversation_id=conversation.id)
    return conversation


def get_conversation(db: Session, conversation_id: int, user_id: int) -> Conversation | None:
    return db.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id, Conversation.user_id == user_id
        )
    )


def save_chat(
    db: Session,
    *,
    conversation: Conversation,
    question: str,
    answer: str | None,
    status: Literal["success", "failed"],
    error_code: str | None = None,
    model: str | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    latency_ms: int | None = None,
) -> Chat:
    """대화방 주인의 ID를 사용하고 대화·방 시각을 함께 commit한다."""
    conversation_id = conversation.id
    chat = Chat(
        user_id=conversation.user_id,
        conversation_id=conversation_id,
        question=question,
        answer=answer,
        status=status,
        error_code=error_code,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
    )
    try:
        db.add(chat)
        conversation.updated_at = func.now()
        db.commit()
        db.refresh(chat)
    except SQLAlchemyError as exc:
        db.rollback()
        log_event(
            logger,
            "db_save_failed",
            logging.ERROR,
            conversation_id=conversation_id,
            operation="save_chat",
            error_type=type(exc).__name__,
        )
        raise
    log_event(logger, "db_save_success", conversation_id=conversation_id, chat_id=chat.id)
    return chat


def get_recent_chats(db: Session, conversation_id: int, limit: int) -> list[Chat]:
    # 오름차순으로 LIMIT하면 가장 오래된 기록이 선택되므로 최신 N개를 먼저 고른다.
    rows = list(
        db.scalars(
            select(Chat)
            .where(Chat.conversation_id == conversation_id, Chat.status == "success")
            .order_by(Chat.created_at.desc(), Chat.id.desc())
            .limit(limit)
        )
    )
    return list(reversed(rows))


def list_conversations(db: Session, user_id: int) -> list[Conversation]:
    return list(
        db.scalars(
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc(), Conversation.id.desc())
        )
    )
