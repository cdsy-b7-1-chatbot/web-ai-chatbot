"""conversations — 대화방. 문맥은 같은 대화방의 최근 대화로 만든다. 설계: #1 ERD."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base

TITLE_MAX_LENGTH = 100


class Conversation(Base):
    __tablename__ = "conversations"
    # 대화방 목록 — 이 사용자의 방을 최근 대화순으로
    __table_args__ = (Index("ix_conversations_user_id_updated_at", "user_id", "updated_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # 다른 모델 파일을 import 하지 않도록 FK 는 테이블 이름 문자열로 가리킨다
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(TITLE_MAX_LENGTH))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # 새 대화가 저장될 때마다 갱신 — 목록 정렬 기준
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
