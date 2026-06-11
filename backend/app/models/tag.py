"""タグモデル。"""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.associations import person_tags
from app.models.environment import DEFAULT_ENVIRONMENT_ID

if TYPE_CHECKING:
    from app.models.person import Person


class Tag(Base):
    __tablename__ = "tags"
    __table_args__ = (UniqueConstraint("environment_id", "name", name="uq_tag_env_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    environment_id: Mapped[int] = mapped_column(
        ForeignKey("environments.id", ondelete="CASCADE"),
        default=DEFAULT_ENVIRONMENT_ID,
        server_default=str(DEFAULT_ENVIRONMENT_ID),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(100), index=True, nullable=False)

    persons: Mapped[list["Person"]] = relationship(secondary=person_tags, back_populates="tags")
