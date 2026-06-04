"""人物モデル。"""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.associations import person_tags

if TYPE_CHECKING:
    from app.models.event import Event
    from app.models.nickname import Nickname
    from app.models.person_external_id import PersonExternalId
    from app.models.person_embedding import PersonEmbedding
    from app.models.photo_person import PhotoPerson
    from app.models.tag import Tag


class Person(Base, TimestampMixin):
    __tablename__ = "persons"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    relation: Mapped[str | None] = mapped_column(String(255))  # 大学の友人 / 前職 / 家族 等
    memo: Mapped[str | None] = mapped_column(Text)

    nicknames: Mapped[list["Nickname"]] = relationship(
        back_populates="person",
        cascade="all, delete-orphan",
        order_by="Nickname.id",
    )
    embeddings: Mapped[list["PersonEmbedding"]] = relationship(
        back_populates="person", cascade="all, delete-orphan"
    )
    external_ids: Mapped[list["PersonExternalId"]] = relationship(
        back_populates="person", cascade="all, delete-orphan"
    )
    photo_links: Mapped[list["PhotoPerson"]] = relationship(
        back_populates="person", cascade="all, delete-orphan"
    )
    tags: Mapped[list["Tag"]] = relationship(secondary=person_tags, back_populates="persons")
    events: Mapped[list["Event"]] = relationship(
        secondary="event_persons", back_populates="persons"
    )
