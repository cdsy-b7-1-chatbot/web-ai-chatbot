"""채팅 HTTP 모델 — ORM 객체와 사용자에게 보낼 필드를 분리한다."""

from datetime import UTC, datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator

from app.core.config import get_settings


def _utc(value: datetime) -> datetime:
    # 테스트 SQLite는 시간대를 버린다. DB 기본 시각은 UTC이므로 응답에서도 UTC로 명시한다.
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


UtcDatetime = Annotated[datetime, AfterValidator(_utc)]


class ChatRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [{"question": "배포 방법을 알려줘", "conversation_id": None}]
        },
    )

    question: str = Field(
        description="앞뒤 공백 제거 후 1~CHAT_MAX_QUESTION_LENGTH자",
        json_schema_extra=lambda schema: schema.update(
            minLength=1, maxLength=get_settings().chat_max_question_length
        ),
    )
    conversation_id: int | None = Field(default=None, gt=0, strict=True)

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        question = value.strip()
        if not 1 <= len(question) <= get_settings().chat_max_question_length:
            raise ValueError("질문은 공백 제거 후 허용 길이 안에 있어야 합니다.")
        return question


class ChatResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "chat_id": 1,
                    "conversation_id": 1,
                    "answer": "배포는 다음 순서로 진행합니다.",
                    "created_at": "2026-10-09T03:00:00Z",
                    "truncated": False,
                }
            ]
        }
    )

    chat_id: int
    conversation_id: int
    answer: str
    created_at: UtcDatetime
    truncated: bool = Field(description="생성 토큰 제한으로 답변이 끝났는지 여부")


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    created_at: UtcDatetime
    updated_at: UtcDatetime


class ConversationListResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "items": [
                        {
                            "id": 1,
                            "title": "배포 방법",
                            "created_at": "2026-10-09T03:00:00Z",
                            "updated_at": "2026-10-09T03:01:00Z",
                        }
                    ]
                }
            ]
        }
    )

    items: list[ConversationResponse]
