from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class User(Base):
    __tablename__ = "t_user"
    __allow_unmapped__ = True

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    username: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    password: Mapped[str] = mapped_column(String(128), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="user")
    avatar: Mapped[str | None] = mapped_column(String(128))
    create_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    update_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    deleted: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)

    nickname: str | None = None
    email: str | None = None
    phone: str | None = None

    def __init__(self, **kwargs: Any) -> None:
        status = kwargs.pop("status", None)
        self.nickname = kwargs.pop("nickname", None)
        self.email = kwargs.pop("email", None)
        self.phone = kwargs.pop("phone", None)
        super().__init__(**kwargs)
        if self.role is None:
            self.role = "user"
        if status is not None:
            self.status = status

    @property
    def status(self) -> int:
        return 1 if self.deleted == 0 else 0

    @status.setter
    def status(self, value: int) -> None:
        self.deleted = 0 if value == 1 else 1
