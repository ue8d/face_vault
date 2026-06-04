"""共起人物 集計キャッシュ。person_a_id < person_b_id で正規化。

写真追加/人物照合時にサービス層で増減更新。数十万枚規模で
都度JOIN集計を避けるための非正規化テーブル。
"""
from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class PersonCooccurrence(Base, TimestampMixin):
    __tablename__ = "person_cooccurrences"
    __table_args__ = (
        UniqueConstraint("person_a_id", "person_b_id", name="uq_cooccurrence_pair"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    person_a_id: Mapped[int] = mapped_column(
        ForeignKey("persons.id", ondelete="CASCADE"), index=True, nullable=False
    )
    person_b_id: Mapped[int] = mapped_column(
        ForeignKey("persons.id", ondelete="CASCADE"), index=True, nullable=False
    )
    count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
