from datetime import datetime

from sqlalchemy import DateTime, Integer, SmallInteger, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin


class Conversation(TimestampMixin, Base):
    __tablename__ = "t_conversation"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    last_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    deleted: Mapped[int] = mapped_column(SmallInteger, default=0)


class Message(TimestampMixin, Base):
    __tablename__ = "t_message"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    thinking_content: Mapped[str | None] = mapped_column(Text)
    thinking_duration: Mapped[int | None] = mapped_column(Integer)
    deleted: Mapped[int] = mapped_column(SmallInteger, default=0)


class ConversationSummary(TimestampMixin, Base):
    __tablename__ = "t_conversation_summary"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    last_message_id: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    deleted: Mapped[int] = mapped_column(SmallInteger, default=0)


class MessageFeedback(Base):
    __tablename__ = "t_message_feedback"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    message_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    conversation_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    vote: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(255))
    comment: Mapped[str | None] = mapped_column(String(1024))
    create_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False),
        server_default=func.now(),
    )
    update_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False),
        server_default=func.now(),
        onupdate=func.now(),
    )
    deleted: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
