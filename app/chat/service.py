"""문맥 → AI → 저장 흐름. HTTP 객체 없이 호출·검증할 수 있게 한다."""

import logging
import time
from collections.abc import Callable
from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.chat import repository
from app.chat.client import AIClientError, AIResult, OpenRouterClient
from app.chat.context import Message, build_messages
from app.chat.schemas import ChatResponse, ConversationListResponse, ConversationResponse
from app.core.config import get_settings
from app.core.errors import AppError, ErrorCode
from app.core.logging import log_event
from app.db.models import Conversation
from app.db.models.conversation import TITLE_MAX_LENGTH

logger = logging.getLogger(__name__)

_AI_ERRORS = {
    "AI_NOT_CONFIGURED": (
        503,
        ErrorCode.AI_NOT_CONFIGURED,
        "AI 설정이 준비되지 않았습니다. 관리자에게 문의해 주세요.",
    ),
    "AI_TIMEOUT": (
        504,
        ErrorCode.AI_TIMEOUT,
        "현재 응답이 지연되고 있어요. 잠시 후 다시 시도해 주세요.",
    ),
    "AI_ERROR": (502, ErrorCode.AI_ERROR, "AI 응답을 받지 못했습니다. 잠시 후 다시 시도해 주세요."),
}
DB_MESSAGE = "대화 기록을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요."


def _room_list(db: Session, user_id: int) -> ConversationListResponse:
    return ConversationListResponse(
        items=[
            ConversationResponse.model_validate(room)
            for room in repository.list_conversations(db, user_id)
        ]
    )


async def get_conversations(db: Session, user_id: int) -> ConversationListResponse:
    return await _db_call("list_conversations", _room_list, db, user_id)


def _app_ai_error(error: AIClientError) -> AppError:
    status, code, message = _AI_ERRORS[error.code]
    return AppError(status, code, message)


async def _db_call[T](operation: str, fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    try:
        # 같은 요청의 Session은 한 번에 한 작업만 수행한다. 이벤트 루프에서 동기 DB를 실행하지 않는다.
        return await run_in_threadpool(fn, *args, **kwargs)
    except SQLAlchemyError as exc:
        if operation not in {"save_chat", "create_conversation"}:
            log_event(
                logger,
                "db_read_failed",
                logging.ERROR,
                operation=operation,
                error_type=type(exc).__name__,
            )
        raise AppError(500, ErrorCode.DB_ERROR, DB_MESSAGE) from None


def _prepare(
    db: Session, user_id: int, question: str, conversation_id: int | None, limit: int
) -> tuple[Conversation, list[Message]]:
    if conversation_id is None:
        room = repository.create_conversation(db, user_id, question[:TITLE_MAX_LENGTH])
    else:
        room = repository.get_conversation(db, conversation_id, user_id)
        if room is None:
            raise AppError(404, ErrorCode.NOT_FOUND, "대화방을 찾을 수 없습니다.")
    recent = repository.get_recent_chats(db, room.id, limit)
    messages = build_messages(recent, question)
    # AI 대기 중에는 읽기 트랜잭션·연결을 붙잡지 않는다. 앱 세션은 expire_on_commit=False다.
    db.commit()
    return room, messages


def _save_success(
    db: Session, room: Conversation, question: str, result: AIResult, latency_ms: int
) -> ChatResponse:
    chat = repository.save_chat(
        db,
        conversation=room,
        question=question,
        answer=result.answer,
        status="success",
        model=result.model,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        latency_ms=latency_ms,
    )
    return ChatResponse(
        chat_id=chat.id,
        conversation_id=chat.conversation_id,
        answer=chat.answer,
        created_at=chat.created_at,
        truncated=result.truncated,
    )


async def send_message(
    db: Session,
    user_id: int,
    question: str,
    conversation_id: int | None,
    ai_client: OpenRouterClient,
) -> ChatResponse:
    try:
        ai_client.ensure_configured()
    except AIClientError as error:
        log_event(logger, "chat_rejected", error_code=error.code)
        raise _app_ai_error(error) from None
    room, messages = await _db_call(
        "prepare_context",
        _prepare,
        db,
        user_id,
        question,
        conversation_id,
        get_settings().chat_context_pairs,
    )
    started = time.perf_counter()
    try:
        result = await ai_client.generate(messages)
    except AIClientError as error:
        latency_ms = round((time.perf_counter() - started) * 1000)
        # 저장 실패로 응답이 바뀌어도 AI 원인을 추적하도록 안전한 코드만 먼저 남긴다.
        log_event(
            logger, "chat_failed", logging.WARNING, conversation_id=room.id, error_code=error.code
        )
        await _db_call(
            "save_chat",
            repository.save_chat,
            db,
            conversation=room,
            question=question,
            answer=None,
            status="failed",
            error_code=error.code,
            model=get_settings().ai_model,
            latency_ms=latency_ms,
        )
        raise _app_ai_error(error) from None
    return await _db_call(
        "save_chat",
        _save_success,
        db,
        room,
        question,
        result,
        round((time.perf_counter() - started) * 1000),
    )
