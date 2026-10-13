"""질문·답변과 실패 상태를 화면에서 확인할 수 있는 기록 응답."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.chat.schemas import UtcDatetime


class ChatHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    conversation_id: int
    question: str
    answer: str | None
    status: Literal["success", "failed"]
    error_code: str | None
    created_at: UtcDatetime


class ChatHistoryListResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "items": [
                        {
                            "id": 1,
                            "user_id": 1,
                            "conversation_id": 1,
                            "question": "배포 방법을 알려줘",
                            "answer": "배포는 다음 순서로 진행합니다.",
                            "status": "success",
                            "error_code": None,
                            "created_at": "2026-10-10T05:00:00Z",
                        }
                    ]
                }
            ]
        }
    )

    items: list[ChatHistoryItem]
