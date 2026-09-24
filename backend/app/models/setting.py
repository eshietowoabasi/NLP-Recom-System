from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from ..extensions import db
from .user import utcnow


class SystemSetting(db.Model):
    """Admin-managed system-wide settings (spec v2 §1: NLP parameter defaults)."""

    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(sa.String(64), primary_key=True)
    value: Mapped[dict] = mapped_column(sa.JSON)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    updated_by: Mapped[int | None] = mapped_column(sa.ForeignKey("users.user_id"))
