"""External IDs used to import people from another database."""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.person import Person


class PersonExternalId(Base):
    __tablename__ = "person_external_ids"
    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_person_external_id_source_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    person_id: Mapped[int] = mapped_column(
        ForeignKey("persons.id", ondelete="CASCADE"), index=True, nullable=False
    )
    source: Mapped[str] = mapped_column(String(100), nullable=False, default="friends_csv")
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)

    person: Mapped["Person"] = relationship(back_populates="external_ids")
