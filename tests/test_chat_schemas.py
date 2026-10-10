from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.chat.schemas import ChatRequest, ChatResponse


def test_question_is_trimmed_before_length_validation(configure):
    configure(chat_max_question_length="3")
    assert ChatRequest(question="  질문!  ").question == "질문!"


@pytest.mark.parametrize("question", ["", " \n\t ", "가" * 5001, 123, None])
def test_bad_question_is_rejected(question):
    with pytest.raises(ValidationError):
        ChatRequest(question=question)


def test_question_at_limit_is_allowed():
    assert len(ChatRequest(question="가" * 5000).question) == 5000


@pytest.mark.parametrize("value", [0, -1, True, "1", 1.5])
def test_conversation_id_must_be_a_positive_integer(value):
    with pytest.raises(ValidationError):
        ChatRequest(question="질문", conversation_id=value)


def test_user_id_cannot_be_injected():
    with pytest.raises(ValidationError):
        ChatRequest(question="질문", user_id=999)


@pytest.mark.parametrize(
    "created_at",
    [
        datetime(2026, 10, 9, 3),
        datetime(2026, 10, 9, 12, tzinfo=timezone(timedelta(hours=9))),
    ],
)
def test_response_time_is_utc(created_at):
    response = ChatResponse(
        chat_id=1, conversation_id=1, answer="답변", created_at=created_at, truncated=False
    )
    assert response.created_at == datetime(2026, 10, 9, 3, tzinfo=UTC)
    assert response.model_dump(mode="json")["created_at"].endswith("Z")
