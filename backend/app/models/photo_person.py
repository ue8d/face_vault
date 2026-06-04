"""写真↔人物 中間（confidence属性あり）。1検出顔=1行。"""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, LargeBinary, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.person import Person
    from app.models.photo import Photo


class PhotoPerson(Base, TimestampMixin):
    __tablename__ = "photo_persons"
    __table_args__ = (UniqueConstraint("photo_id", "person_id", name="uq_photo_person"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    photo_id: Mapped[int] = mapped_column(
        ForeignKey("photos.id", ondelete="CASCADE"), index=True, nullable=False
    )
    person_id: Mapped[int | None] = mapped_column(
        ForeignKey("persons.id", ondelete="SET NULL"), index=True
    )  # NULL = 未照合の検出顔
    confidence: Mapped[float | None] = mapped_column(Float)  # 照合スコア
    # 検出顔のEmbedding（FAISS再構築/再照合用）。ArcFace 512次元 float32 = 2048 bytes
    embedding: Mapped[bytes | None] = mapped_column(LargeBinary)
    # 顔バウンディングボックス "x,y,w,h"
    bbox: Mapped[str | None] = mapped_column(String(64))

    photo: Mapped["Photo"] = relationship(back_populates="person_links")
    person: Mapped["Person | None"] = relationship(back_populates="photo_links")

    @property
    def person_name(self) -> str | None:
        return self.person.name if self.person else None
