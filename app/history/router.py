"""기존 쿠키·Bearer 인증을 사용하는 내 기록 조회 API."""

from typing import Annotated

from fastapi import APIRouter, Query

from app.auth.dependencies import CurrentUser
from app.core.errors import error_responses
from app.db.database import SessionDep
from app.history import service
from app.history.schemas import ChatHistoryListResponse

router = APIRouter(prefix="/api/me", tags=["대화 기록"])


@router.get("/chats", responses=error_responses(401, 404, 422, 500))
def my_chats(
    user: CurrentUser,
    db: SessionDep,
    conversation_id: Annotated[int | None, Query(gt=0, description="선택한 대화방 ID")] = None,
    limit: Annotated[int, Query(ge=1, le=100, description="한 번에 조회할 개수")] = 50,
    offset: Annotated[int, Query(ge=0, description="건너뛸 기록 개수")] = 0,
) -> ChatHistoryListResponse:
    """실패를 포함한 내 기록을 최신순(created_at DESC, id DESC)으로 반환한다.

    conversation_id를 생략하면 내 전체 기록을 조회한다. 없는 방과 다른 사용자 방은 404다.
    화면에 시간순으로 표시할 때는 받은 기록의 순서를 뒤집는다. AI 키 없이 동작한다.
    """
    return service.get_chats(db, user.id, limit, offset, conversation_id=conversation_id)
