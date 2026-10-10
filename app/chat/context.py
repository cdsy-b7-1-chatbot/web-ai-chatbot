"""문맥 메시지 구성 — 실패 기록 제외와 소유권 검사는 repository·service가 맡는다."""

from typing import Literal, TypedDict

from app.db.models import Chat

SYSTEM_PROMPT = (
    "당신은 질문, 설명, 요약을 돕는 범용 AI 도우미입니다. "
    "사용자가 다른 언어를 요청하지 않으면 한국어로 간결하고 이해하기 쉽게 답하세요. "
    "이전 대화를 참고하되 모르는 사실은 추측하지 말고 불확실함을 알려 주세요."
)


class Message(TypedDict):
    role: Literal["system", "user", "assistant"]
    content: str


def build_messages(chats: list[Chat], question: str) -> list[Message]:
    messages: list[Message] = [{"role": "system", "content": SYSTEM_PROMPT}]
    for chat in chats:
        if chat.status == "success" and chat.answer:
            messages.extend(
                [
                    {"role": "user", "content": chat.question},
                    {"role": "assistant", "content": chat.answer},
                ]
            )
    messages.append({"role": "user", "content": question})
    return messages
