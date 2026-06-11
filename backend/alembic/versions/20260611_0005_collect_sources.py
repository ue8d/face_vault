"""Add collect_sources and collected_urls tables (auto image collection).

収集元ドメインと収集済みURLを環境スコープで管理する。

Revision ID: 20260611_0005
Revises: 20260611_0004
Create Date: 2026-06-11
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260611_0005"
down_revision = "20260611_0004"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    return inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if not _has_table("collect_sources"):
        op.create_table(
            "collect_sources",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("environment_id", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("start_url", sa.Text(), nullable=False),
            sa.Column("crawl_mode", sa.String(length=16), nullable=False, server_default="page"),
            sa.Column("max_pages", sa.Integer(), nullable=False, server_default="20"),
            sa.Column("max_images", sa.Integer(), nullable=False, server_default="100"),
            sa.Column("same_domain_only", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("respect_robots", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("interval_minutes", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_status", sa.String(length=16), nullable=True),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column(
                "created_at", sa.DateTime(timezone=True),
                server_default=sa.func.now(), nullable=False,
            ),
            sa.Column(
                "updated_at", sa.DateTime(timezone=True),
                server_default=sa.func.now(), nullable=False,
            ),
            sa.ForeignKeyConstraint(["environment_id"], ["environments.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_collect_sources_environment_id", "collect_sources", ["environment_id"]
        )
        op.create_index("ix_collect_sources_next_run_at", "collect_sources", ["next_run_at"])

    if not _has_table("collected_urls"):
        op.create_table(
            "collected_urls",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("environment_id", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("source_id", sa.Integer(), nullable=True),
            sa.Column("url", sa.Text(), nullable=False),
            sa.Column("photo_id", sa.Integer(), nullable=True),
            sa.Column(
                "created_at", sa.DateTime(timezone=True),
                server_default=sa.func.now(), nullable=False,
            ),
            sa.ForeignKeyConstraint(["environment_id"], ["environments.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["source_id"], ["collect_sources.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["photo_id"], ["photos.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("environment_id", "url", name="uq_collected_url_env_url"),
        )
        op.create_index(
            "ix_collected_urls_environment_id", "collected_urls", ["environment_id"]
        )
        op.create_index("ix_collected_urls_source_id", "collected_urls", ["source_id"])


def downgrade() -> None:
    if _has_table("collected_urls"):
        op.drop_table("collected_urls")
    if _has_table("collect_sources"):
        op.drop_table("collect_sources")
