from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column


class TimestampMixin:
    create_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False),
        server_default=func.now(),
    )
    update_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False),
        server_default=func.now(),
        onupdate=func.now(),
    )
