"""로그인한 사용자의 채팅 HTTP 입출력."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.auth.dependencies import CurrentUser
from app.chat import service
from app.chat.client import OpenRouterClient, get_ai_client
from app.chat.schemas import ChatRequest, ChatResponse, ConversationListResponse
from app.core.errors import error_responses
from app.db.database import SessionDep

router = APIRouter(prefix="/api", tags=["채팅"])
AIClientDep = Annotated[OpenRouterClient, Depends(get_ai_client)]


@router.get("/conversations", responses=error_responses(401, 500))
async def conversations(user: CurrentUser, db: SessionDep) -> ConversationListResponse:
    """내 대화방을 최근 활동순으로 반환한다. 첫 버전은 페이징 없이 제공한다."""
    return await service.get_conversations(db, user.id)


@router.post("/chat", responses=error_responses(401, 404, 422, 500, 502, 503, 504))
async def chat(
    body: ChatRequest, user: CurrentUser, db: SessionDep, ai: AIClientDep
) -> ChatResponse:
    """같은 방의 최근 성공 Q/A로 답변하고 저장이 끝나면 반환한다.

    conversation_id를 생략하면 새 방을 만든다. AI 실패 기록은 저장하지만 문맥에서는 제외한다.
    저장 실패는 오류로 반환하며, 생성된 답변을 정상 결과로 보내지 않는다.
    """
    return await service.send_message(db, user.id, body.question, body.conversation_id, ai)
