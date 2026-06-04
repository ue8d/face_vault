"""写真↔人物 中間（confidence属性あり）。1検出顔=1行。

埋め込みは face_embeddings 子テーブル（モデル別）に保持。
.embedding プロパティは insightface 埋め込みの後方互換読み取り用。
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.face.embedder import INSIGHTFACE

if TYPE_CHECKING:
    from app.models.face_embedding import FaceEmbedding
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
    # 顔バウンディングボックス "x,y,w,h"
    bbox: Mapped[str | None] = mapped_column(String(64))

    photo: Mapped["Photo"] = relationship(back_populates="person_links")
    person: Mapped["Person | None"] = relationship(back_populates="photo_links")
    embeddings: Mapped[list["FaceEmbedding"]] = relationship(
        back_populates="photo_person", cascade="all, delete-orphan"
    )

    @property
    def person_name(self) -> str | None:
        return self.person.name if self.person else None

    @property
    def embedding(self) -> bytes | None:
        """後方互換: insightface 埋め込みのバイト列（無ければ任意の1件）。"""
        by_model = {fe.model_key: fe.embedding for fe in self.embeddings}
        if INSIGHTFACE in by_model:
            return by_model[INSIGHTFACE]
        return next(iter(by_model.values()), None)

    @embedding.setter
    def embedding(self, value: bytes | None) -> None:
        """後方互換: PhotoPerson(embedding=...) を insightface 子行に変換する。"""
        from app.models.face_embedding import FaceEmbedding

        self.embeddings = [
            fe for fe in self.embeddings if fe.model_key != INSIGHTFACE
        ]
        if value is not None:
            self.embeddings.append(
                FaceEmbedding(
                    model_key=INSIGHTFACE,
                    embedding=value,
                    dim=len(value) // 4,
                )
            )
