"""Add learned_person_id to api_queries.

Revision ID: 20260608_0003
Revises: 20260608_0002
Create Date: 2026-06-08
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260608_0003"
down_revision = "20260608_0002"
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    return {col["name"] for col in inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    if "learned_person_id" in _columns("api_queries"):
        return
    with op.batch_alter_table("api_queries") as batch_op:
        batch_op.add_column(sa.Column("learned_person_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_api_queries_learned_person",
            "persons",
            ["learned_person_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    if "learned_person_id" not in _columns("api_queries"):
        return
    with op.batch_alter_table("api_queries") as batch_op:
        batch_op.drop_constraint("fk_api_queries_learned_person", type_="foreignkey")
        batch_op.drop_column("learned_person_id")
