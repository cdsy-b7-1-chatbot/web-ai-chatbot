"""대화방·대화 저장과 조회. HTTP 오류 변환은 service가 담당한다."""

import logging

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.logging import log_event
from app.db.models import Conversation

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
