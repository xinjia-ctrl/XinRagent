from sqlalchemy import BigInteger, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin


class KnowledgeBase(TimestampMixin, Base):
    __tablename__ = "t_knowledge_base"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    visibility: Mapped[str] = mapped_column(String(32), nullable=False, default="private")
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[int | None] = mapped_column(BigInteger, index=True)


class KnowledgeDocument(TimestampMixin, Base):
    __tablename__ = "t_knowledge_document"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    kb_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("t_knowledge_base.id"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    file_name: Mapped[str | None] = mapped_column(String(255))
    file_type: Mapped[str | None] = mapped_column(String(32))
    file_size: Mapped[int | None] = mapped_column(BigInteger)
    storage_path: Mapped[str | None] = mapped_column(String(1024))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    error_message: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict | None] = mapped_column(JSON)


class KnowledgeChunk(TimestampMixin, Base):
    __tablename__ = "t_knowledge_chunk"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    kb_id: Mapped[str] = mapped_column(String(64), ForeignKey("t_knowledge_base.id"), index=True)
    doc_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("t_knowledge_document.id"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int | None] = mapped_column(Integer)
    metadata_json: Mapped[dict | None] = mapped_column(JSON)


class KnowledgeVector(TimestampMixin, Base):
    __tablename__ = "t_knowledge_vector"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    kb_id: Mapped[str] = mapped_column(String(64), ForeignKey("t_knowledge_base.id"), index=True)
    chunk_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("t_knowledge_chunk.id"),
        nullable=False,
        index=True,
    )
    embedding: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_model: Mapped[str | None] = mapped_column(String(128))
    dimension: Mapped[int | None] = mapped_column(Integer)
