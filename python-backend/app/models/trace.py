from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin


class RagTraceRun(TimestampMixin, Base):
    __tablename__ = "t_rag_trace_run"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    trace_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    trace_name: Mapped[str | None] = mapped_column(String(128))
    entry_method: Mapped[str | None] = mapped_column(String(256))
    conversation_id: Mapped[str | None] = mapped_column(String(20), index=True)
    task_id: Mapped[str | None] = mapped_column(String(20), index=True)
    user_id: Mapped[str | None] = mapped_column(String(20), index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="RUNNING")
    error_message: Mapped[str | None] = mapped_column(String(1000))
    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    duration_ms: Mapped[int | None] = mapped_column(BigInteger)
    extra_data: Mapped[str | None] = mapped_column(Text)
    deleted: Mapped[int] = mapped_column(SmallInteger, default=0)


class RagTraceNode(TimestampMixin, Base):
    __tablename__ = "t_rag_trace_node"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    trace_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    node_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    parent_node_id: Mapped[str | None] = mapped_column(String(20))
    depth: Mapped[int | None] = mapped_column(Integer, default=0)
    node_type: Mapped[str | None] = mapped_column(String(16))
    node_name: Mapped[str | None] = mapped_column(String(128))
    class_name: Mapped[str | None] = mapped_column(String(256))
    method_name: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="RUNNING")
    error_message: Mapped[str | None] = mapped_column(String(1000))
    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    duration_ms: Mapped[int | None] = mapped_column(BigInteger)
    extra_data: Mapped[str | None] = mapped_column(Text)
    deleted: Mapped[int] = mapped_column(SmallInteger, default=0)
