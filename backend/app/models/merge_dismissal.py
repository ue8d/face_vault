"""統合候補の「別人」却下記録（再提案を防ぐ）。person_a_id < person_b_id で正規化。"""
from __future__ import annotations

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MergeDismissal(Base):
    __tablename__ = "merge_dismissals"

    person_a_id: Mapped[int] = mapped_column(
        ForeignKey("persons.id", ondelete="CASCADE"), primary_key=True
    )
    person_b_id: Mapped[int] = mapped_column(
        ForeignKey("persons.id", ondelete="CASCADE"), primary_key=True
    )
