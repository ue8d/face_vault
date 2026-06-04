"""イベントモデル。"""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.associations import event_persons

if TYPE_CHECKING:
    from app.models.person import Person
    from app.models.photo import Photo


class Event(Base, TimestampMixin):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True, nullable=False)  # GW飲み会 等
    memo: Mapped[str | None] = mapped_column(Text)

    photos: Mapped[list["Photo"]] = relationship(back_populates="event")
    persons: Mapped[list["Person"]] = relationship(
        secondary=event_persons, back_populates="events"
    )
