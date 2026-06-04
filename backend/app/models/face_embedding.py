"""検出顔ごと・モデルごとの埋め込み。1 photo_person × model_key = 1行。

マルチモデル運用の正本。photo_persons.embedding（旧・単一列）を置き換える。
各モデルは別空間 → モデル別 VectorIndex / 別 person_embeddings.model_key と対応。
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, LargeBinary, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.photo_person import PhotoPerson


class FaceEmbedding(Base, TimestampMixin):
    __tablename__ = "face_embeddings"
    __table_args__ = (
        UniqueConstraint("photo_person_id", "model_key", name="uq_face_embedding_model"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    photo_person_id: Mapped[int] = mapped_column(
        ForeignKey("photo_persons.id", ondelete="CASCADE"), index=True, nullable=False
    )
    model_key: Mapped[str] = mapped_column(String(32), nullable=False)
    embedding: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    dim: Mapped[int] = mapped_column(Integer, default=512, nullable=False)

    photo_person: Mapped["PhotoPerson"] = relationship(back_populates="embeddings")
