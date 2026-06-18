from sqlalchemy import Integer, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin


class SampleQuestion(TimestampMixin, Base):
    __tablename__ = "t_sample_question"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    title: Mapped[str | None] = mapped_column(String(64))
    description: Mapped[str | None] = mapped_column(String(255))
    question: Mapped[str] = mapped_column(String(255), nullable=False)
    deleted: Mapped[int] = mapped_column(SmallInteger, default=0)


class QueryTermMapping(TimestampMixin, Base):
    __tablename__ = "t_query_term_mapping"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    domain: Mapped[str | None] = mapped_column(String(64))
    source_term: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    target_term: Mapped[str] = mapped_column(String(128), nullable=False)
    match_type: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    enabled: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    remark: Mapped[str | None] = mapped_column(String(255))
    create_by: Mapped[str | None] = mapped_column(String(20))
    update_by: Mapped[str | None] = mapped_column(String(20))
    deleted: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
