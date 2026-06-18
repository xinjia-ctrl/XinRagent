from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin
from app.models.types import PgVector


class KnowledgeBase(TimestampMixin, Base):
    __tablename__ = "t_knowledge_base"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(64), nullable=False)
    collection_name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_by: Mapped[str] = mapped_column(String(20), nullable=False)
    updated_by: Mapped[str | None] = mapped_column(String(20))
    deleted: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)


class KnowledgeDocument(TimestampMixin, Base):
    __tablename__ = "t_knowledge_document"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    kb_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    doc_name: Mapped[str] = mapped_column(String(256), nullable=False)
    enabled: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    chunk_count: Mapped[int | None] = mapped_column(Integer, default=0)
    file_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_type: Mapped[str] = mapped_column(String(16), nullable=False)
    file_size: Mapped[int | None] = mapped_column(BigInteger)
    process_mode: Mapped[str | None] = mapped_column(String(16), default="chunk")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    source_type: Mapped[str | None] = mapped_column(String(16))
    source_location: Mapped[str | None] = mapped_column(String(1024))
    schedule_enabled: Mapped[int | None] = mapped_column(SmallInteger)
    schedule_cron: Mapped[str | None] = mapped_column(String(64))
    chunk_strategy: Mapped[str | None] = mapped_column(String(32))
    chunk_config: Mapped[dict | None] = mapped_column(JSONB)
    pipeline_id: Mapped[str | None] = mapped_column(String(20))
    created_by: Mapped[str] = mapped_column(String(20), nullable=False)
    updated_by: Mapped[str | None] = mapped_column(String(20))
    deleted: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)


class KnowledgeChunk(TimestampMixin, Base):
    __tablename__ = "t_knowledge_chunk"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    kb_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    doc_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str | None] = mapped_column(String(64))
    char_count: Mapped[int | None] = mapped_column(Integer)
    token_count: Mapped[int | None] = mapped_column(Integer)
    enabled: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    created_by: Mapped[str] = mapped_column(String(20), nullable=False)
    updated_by: Mapped[str | None] = mapped_column(String(20))
    deleted: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)


class KnowledgeDocumentChunkLog(Base):
    __tablename__ = "t_knowledge_document_chunk_log"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    doc_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    process_mode: Mapped[str | None] = mapped_column(String(16))
    chunk_strategy: Mapped[str | None] = mapped_column(String(16))
    pipeline_id: Mapped[str | None] = mapped_column(String(20))
    extract_duration: Mapped[int | None] = mapped_column(BigInteger)
    chunk_duration: Mapped[int | None] = mapped_column(BigInteger)
    embed_duration: Mapped[int | None] = mapped_column(BigInteger)
    persist_duration: Mapped[int | None] = mapped_column(BigInteger)
    total_duration: Mapped[int | None] = mapped_column(BigInteger)
    chunk_count: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text)
    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    create_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    update_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))


class KnowledgeDocumentSchedule(TimestampMixin, Base):
    __tablename__ = "t_knowledge_document_schedule"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    doc_id: Mapped[str] = mapped_column(String(20), nullable=False, unique=True, index=True)
    kb_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    cron_expr: Mapped[str | None] = mapped_column(String(64))
    enabled: Mapped[int | None] = mapped_column(SmallInteger, default=0)
    next_run_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    last_run_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    last_success_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    last_status: Mapped[str | None] = mapped_column(String(16))
    last_error: Mapped[str | None] = mapped_column(String(512))
    last_etag: Mapped[str | None] = mapped_column(String(256))
    last_modified: Mapped[str | None] = mapped_column(String(256))
    last_content_hash: Mapped[str | None] = mapped_column(String(128))
    lock_owner: Mapped[str | None] = mapped_column(String(128))
    lock_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))


class KnowledgeDocumentScheduleExec(TimestampMixin, Base):
    __tablename__ = "t_knowledge_document_schedule_exec"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    schedule_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    doc_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    kb_id: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    message: Mapped[str | None] = mapped_column(String(512))
    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    file_name: Mapped[str | None] = mapped_column(String(512))
    file_size: Mapped[int | None] = mapped_column(BigInteger)
    content_hash: Mapped[str | None] = mapped_column(String(128))
    etag: Mapped[str | None] = mapped_column(String(256))
    last_modified: Mapped[str | None] = mapped_column(String(256))


class KnowledgeVector(Base):
    __tablename__ = "t_knowledge_vector"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    content: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict | None] = mapped_column("metadata", JSONB)
    embedding: Mapped[list[float] | None] = mapped_column(PgVector(1536))
