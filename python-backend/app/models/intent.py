from sqlalchemy import Integer, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin


class IntentNode(TimestampMixin, Base):
    __tablename__ = "t_intent_node"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    kb_id: Mapped[str | None] = mapped_column(String(20))
    intent_code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    level: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    parent_code: Mapped[str | None] = mapped_column(String(64))
    description: Mapped[str | None] = mapped_column(String(512))
    examples: Mapped[str | None] = mapped_column(Text)
    collection_name: Mapped[str | None] = mapped_column(String(128))
    top_k: Mapped[int | None] = mapped_column(Integer)
    mcp_tool_id: Mapped[str | None] = mapped_column(String(128))
    kind: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    prompt_snippet: Mapped[str | None] = mapped_column(Text)
    prompt_template: Mapped[str | None] = mapped_column(Text)
    param_prompt_template: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    enabled: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    create_by: Mapped[str | None] = mapped_column(String(20))
    update_by: Mapped[str | None] = mapped_column(String(20))
    deleted: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
