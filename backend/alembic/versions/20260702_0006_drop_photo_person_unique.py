"""Drop uq_photo_person unique constraint (allow same person multiple times in one photo).

1枚の写真に同一人物が複数回検出されるケース（集合写真での重複登場等）を
許容するため、(photo_id, person_id) の一意制約を削除する。

Revision ID: 20260702_0006
Revises: 20260611_0005
Create Date: 2026-07-02
"""
from __future__ import annotations

from alembic import op
from sqlalchemy import inspect


revision = "20260702_0006"
down_revision = "20260611_0005"
branch_labels = None
depends_on = None

CONSTRAINT_NAME = "uq_photo_person"


def _has_constraint(table: str, name: str) -> bool:
    inspector = inspect(op.get_bind())
    return any(
        uc["name"] == name for uc in inspector.get_unique_constraints(table)
    )


def upgrade() -> None:
    if _has_constraint("photo_persons", CONSTRAINT_NAME):
        with op.batch_alter_table("photo_persons") as batch_op:
            batch_op.drop_constraint(CONSTRAINT_NAME, type_="unique")


def downgrade() -> None:
    if not _has_constraint("photo_persons", CONSTRAINT_NAME):
        with op.batch_alter_table("photo_persons") as batch_op:
            batch_op.create_unique_constraint(
                CONSTRAINT_NAME, ["photo_id", "person_id"]
            )
