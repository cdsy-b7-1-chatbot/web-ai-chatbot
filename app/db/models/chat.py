"""chats — 질문·응답 한 쌍이 한 행. 설계: #1 ERD.

- AI 실패도 저장한다(status=failed, error_code) — 사용자 기준으로 실패 이력까지 추적
- user_id 는 conversations 를 거쳐 알 수 있지만 일부러 둔다(비정규화) — 로그는 추가만 되고 대화방 주인도
  바뀌지 않아 어긋날 일이 없고, 사용자 기준 조회가 JOIN 없이 끝난다. 저장할 때 대화방의 user_id 를 그대로 쓴다
- 사용량(model·토큰·latency_ms)은 실패 시 비어 있을 수 있다. 합계·비용은 계산으로 얻으므로 저장하지 않는다
"""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base

STATUSES = ("success", "failed")


class Chat(Base):
    __tablename__ = "chats"
    __table_args__ = (
        CheckConstraint("status IN ('success', 'failed')", name="ck_chats_status"),
        # 문맥용 — 같은 대화방의 최근 N개
        Index("ix_chats_conversation_id_created_at", "conversation_id", "created_at"),
        # 사용자 기준 로그 — 이 사용자의 최근 기록
        Index("ix_chats_user_id_created_at", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"))
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(10))
    error_code: Mapped[str | None] = mapped_column(String(50))
    model: Mapped[str | None] = mapped_column(String(100))
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
