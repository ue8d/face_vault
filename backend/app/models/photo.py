"""写真モデル。"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.environment import DEFAULT_ENVIRONMENT_ID

if TYPE_CHECKING:
    from app.models.event import Event
    from app.models.photo_person import PhotoPerson


class Photo(Base, TimestampMixin):
    __tablename__ = "photos"

    id: Mapped[int] = mapped_column(primary_key=True)
    environment_id: Mapped[int] = mapped_column(
        ForeignKey("environments.id", ondelete="CASCADE"),
        default=DEFAULT_ENVIRONMENT_ID,
        server_default=str(DEFAULT_ENVIRONMENT_ID),
        index=True,
        nullable=False,
    )
    path: Mapped[str] = mapped_column(String(1024), nullable=False)  # ストレージ相対パス
    taken_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    memo: Mapped[str | None] = mapped_column(Text)
    event_id: Mapped[int | None] = mapped_column(
        ForeignKey("events.id", ondelete="SET NULL"), index=True
    )

    event: Mapped["Event | None"] = relationship(back_populates="photos")
    person_links: Mapped[list["PhotoPerson"]] = relationship(
        back_populates="photo", cascade="all, delete-orphan"
    )
