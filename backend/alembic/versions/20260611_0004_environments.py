"""Add environments table and environment_id scoping columns.

persons / photos / events / tags / api_queries / person_external_ids を
環境（テナント）単位で分離する。既存データは default 環境(id=1)へ帰属。

Revision ID: 20260611_0004
Revises: 20260608_0003
Create Date: 2026-06-11
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260611_0004"
down_revision = "20260608_0003"
branch_labels = None
depends_on = None

SCOPED_TABLES = (
    "persons",
    "photos",
    "events",
    "tags",
    "api_queries",
    "person_external_ids",
)


def _insp():
    return inspect(op.get_bind())


def _has_table(name: str) -> bool:
    return _insp().has_table(name)


def _columns(table: str) -> set[str]:
    return {col["name"] for col in _insp().get_columns(table)}


def _unique_constraints(table: str) -> set[str]:
    try:
        return {uc["name"] for uc in _insp().get_unique_constraints(table) if uc["name"]}
    except NotImplementedError:  # pragma: no cover
        return set()


def upgrade() -> None:
    if not _has_table("environments"):
        op.create_table(
            "environments",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("name"),
        )
    # 既存データの帰属先 default 環境（id=1）
    op.execute(
        "INSERT INTO environments (id, name, created_at, updated_at) "
        "SELECT 1, 'default', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP "
        "WHERE NOT EXISTS (SELECT 1 FROM environments WHERE id = 1)"
    )

    for table in SCOPED_TABLES:
        if not _has_table(table) or "environment_id" in _columns(table):
            continue
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "environment_id",
                    sa.Integer(),
                    nullable=False,
                    server_default="1",
                )
            )
            batch_op.create_foreign_key(
                f"fk_{table}_environment",
                "environments",
                ["environment_id"],
                ["id"],
                ondelete="CASCADE",
            )
        op.create_index(f"ix_{table}_environment_id", table, ["environment_id"])

    # tags.name のグローバル一意 → (environment_id, name) 一意へ
    if _has_table("tags") and "uq_tag_env_name" not in _unique_constraints("tags"):
        with op.batch_alter_table("tags") as batch_op:
            for name in ("tags_name_key", "uq_tags_name"):
                if name in _unique_constraints("tags"):
                    batch_op.drop_constraint(name, type_="unique")
            batch_op.create_unique_constraint("uq_tag_env_name", ["environment_id", "name"])

    # person_external_ids: (source, external_id) → (environment_id, source, external_id)
    if (
        _has_table("person_external_ids")
        and "uq_person_external_id_source_id" in _unique_constraints("person_external_ids")
    ):
        with op.batch_alter_table("person_external_ids") as batch_op:
            batch_op.drop_constraint("uq_person_external_id_source_id", type_="unique")
            batch_op.create_unique_constraint(
                "uq_person_external_id_source_id",
                ["environment_id", "source", "external_id"],
            )


def downgrade() -> None:
    for table in SCOPED_TABLES:
        if not _has_table(table) or "environment_id" not in _columns(table):
            continue
        op.drop_index(f"ix_{table}_environment_id", table_name=table)
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_constraint(f"fk_{table}_environment", type_="foreignkey")
            batch_op.drop_column("environment_id")
    if _has_table("environments"):
        op.drop_table("environments")
