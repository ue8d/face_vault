"""人物Embedding（代表ベクトル群）。FAISSインデックスの正本。"""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, LargeBinary
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.person import Person


class PersonEmbedding(Base, TimestampMixin):
    __tablename__ = "person_embeddings"

    id: Mapped[int] = mapped_column(primary_key=True)
    person_id: Mapped[int] = mapped_column(
        ForeignKey("persons.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # ArcFace 512次元 float32 のバイト列。FAISS id = この行のid
    embedding: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    dim: Mapped[int] = mapped_column(Integer, default=512, nullable=False)
    # 由来写真（任意）
    source_photo_id: Mapped[int | None] = mapped_column(
        ForeignKey("photos.id", ondelete="SET NULL")
    )

    person: Mapped["Person"] = relationship(back_populates="embeddings")
