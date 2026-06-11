"""External IDs used to import people from another database."""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.environment import DEFAULT_ENVIRONMENT_ID

if TYPE_CHECKING:
    from app.models.person import Person


class PersonExternalId(Base):
    __tablename__ = "person_external_ids"
    __table_args__ = (
        UniqueConstraint(
            "environment_id", "source", "external_id",
            name="uq_person_external_id_source_id",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    environment_id: Mapped[int] = mapped_column(
        ForeignKey("environments.id", ondelete="CASCADE"),
        default=DEFAULT_ENVIRONMENT_ID,
        server_default=str(DEFAULT_ENVIRONMENT_ID),
        index=True,
        nullable=False,
    )
    person_id: Mapped[int] = mapped_column(
        ForeignKey("persons.id", ondelete="CASCADE"), index=True, nullable=False
    )
    source: Mapped[str] = mapped_column(String(100), nullable=False, default="friends_csv")
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)

    person: Mapped["Person"] = relationship(back_populates="external_ids")
