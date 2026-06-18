from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin


class IngestionPipeline(TimestampMixin, Base):
    __tablename__ = "t_ingestion_pipeline"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str | None] = mapped_column(String(20), default="")
    updated_by: Mapped[str | None] = mapped_column(String(20), default="")
    deleted: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)


class IngestionPipelineNode(TimestampMixin, Base):
    __tablename__ = "t_ingestion_pipeline_node"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    pipeline_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    node_id: Mapped[str] = mapped_column(String(20), nullable=False)
    node_type: Mapped[str] = mapped_column(String(16), nullable=False)
    next_node_id: Mapped[str | None] = mapped_column(String(20))
    settings_json: Mapped[dict | None] = mapped_column(JSONB)
    condition_json: Mapped[dict | None] = mapped_column(JSONB)
    created_by: Mapped[str | None] = mapped_column(String(20), default="")
    updated_by: Mapped[str | None] = mapped_column(String(20), default="")
    deleted: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)


class IngestionTask(TimestampMixin, Base):
    __tablename__ = "t_ingestion_task"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    pipeline_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    source_location: Mapped[str | None] = mapped_column(Text)
    source_file_name: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    chunk_count: Mapped[int | None] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    logs_json: Mapped[list | None] = mapped_column(JSONB)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    created_by: Mapped[str | None] = mapped_column(String(20), default="")
    updated_by: Mapped[str | None] = mapped_column(String(20), default="")
    deleted: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)


class IngestionTaskNode(TimestampMixin, Base):
    __tablename__ = "t_ingestion_task_node"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    pipeline_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    node_id: Mapped[str] = mapped_column(String(20), nullable=False)
    node_type: Mapped[str] = mapped_column(String(16), nullable=False)
    node_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    duration_ms: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    message: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    output_json: Mapped[str | None] = mapped_column(Text)
    deleted: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
