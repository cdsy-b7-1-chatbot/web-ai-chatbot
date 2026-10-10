"""기록은 로그인 사용자 범위에서만 조회하고 DB 오류는 공통 형식으로 반환한다."""

import logging

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.chat.repository import get_conversation
from app.core.errors import AppError, ErrorCode
from app.core.logging import log_event
from app.history import repository
from app.history.schemas import ChatHistoryItem, ChatHistoryListResponse

logger = logging.getLogger(__name__)


def get_chats(
    db: Session,
    user_id: int,
    limit: int = 50,
    offset: int = 0,
    *,
    conversation_id: int | None = None,
) -> ChatHistoryListResponse:
    try:
        if conversation_id is not None and get_conversation(db, conversation_id, user_id) is None:
            # 다른 사용자의 방과 없는 방은 같은 응답으로 처리한다.
            raise AppError(404, ErrorCode.NOT_FOUND, "대화방을 찾을 수 없습니다.")
        items = [
            ChatHistoryItem.model_validate(chat)
            for chat in repository.list_chats(
                db, user_id, limit, offset, conversation_id=conversation_id
            )
        ]
    except SQLAlchemyError as exc:
        db.rollback()
        log_event(
            logger,
            "db_read_failed",
            logging.ERROR,
            operation="list_chats",
            error_type=type(exc).__name__,
        )
        raise AppError(
            500, ErrorCode.DB_ERROR, "대화 기록을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요."
        ) from None
    log_event(logger, "history_read_success", conversation_id=conversation_id, count=len(items))
    return ChatHistoryListResponse(items=items)
