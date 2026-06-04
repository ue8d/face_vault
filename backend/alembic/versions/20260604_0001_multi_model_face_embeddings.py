"""Add multi-model face embeddings.

Revision ID: 20260604_0001
Revises:
Create Date: 2026-06-04
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260604_0001"
down_revision = None
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    return inspect(op.get_bind()).has_table(name)


def _columns(table: str) -> set[str]:
    return {col["name"] for col in inspect(op.get_bind()).get_columns(table)}


def _embedding_dim_expr() -> str:
    if op.get_context().dialect.name == "postgresql":
        return "octet_length(embedding) / 4"
    return "length(embedding) / 4"


def upgrade() -> None:
    if _has_table("person_embeddings") and "model_key" not in _columns(
        "person_embeddings"
    ):
        op.add_column(
            "person_embeddings",
            sa.Column(
                "model_key",
                sa.String(length=32),
                server_default="insightface",
                nullable=False,
            ),
        )
        op.create_index(
            "ix_person_embeddings_model_key",
            "person_embeddings",
            ["model_key"],
            unique=False,
        )

    if _has_table("photo_persons") and not _has_table("face_embeddings"):
        op.create_table(
            "face_embeddings",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("photo_person_id", sa.Integer(), nullable=False),
            sa.Column("model_key", sa.String(length=32), nullable=False),
            sa.Column("embedding", sa.LargeBinary(), nullable=False),
            sa.Column("dim", sa.Integer(), nullable=False, server_default="512"),
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
            sa.ForeignKeyConstraint(
                ["photo_person_id"], ["photo_persons.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "photo_person_id", "model_key", name="uq_face_embedding_model"
            ),
        )
        op.create_index(
            "ix_face_embeddings_photo_person_id",
            "face_embeddings",
            ["photo_person_id"],
            unique=False,
        )

    if _has_table("photo_persons") and "embedding" in _columns("photo_persons"):
        dim_expr = _embedding_dim_expr()
        op.execute(
            sa.text(
                f"""
                INSERT INTO face_embeddings
                    (photo_person_id, model_key, embedding, dim, created_at, updated_at)
                SELECT
                    id,
                    'insightface',
                    embedding,
                    {dim_expr},
                    CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP
                FROM photo_persons
                WHERE embedding IS NOT NULL
                """
            )
        )
        with op.batch_alter_table("photo_persons") as batch_op:
            batch_op.drop_column("embedding")


def downgrade() -> None:
    if _has_table("photo_persons") and "embedding" not in _columns("photo_persons"):
        with op.batch_alter_table("photo_persons") as batch_op:
            batch_op.add_column(sa.Column("embedding", sa.LargeBinary(), nullable=True))
        if _has_table("face_embeddings"):
            op.execute(
                sa.text(
                    """
                    UPDATE photo_persons
                    SET embedding = (
                        SELECT face_embeddings.embedding
                        FROM face_embeddings
                        WHERE face_embeddings.photo_person_id = photo_persons.id
                          AND face_embeddings.model_key = 'insightface'
                        LIMIT 1
                    )
                    """
                )
            )

    if _has_table("face_embeddings"):
        op.drop_index(
            "ix_face_embeddings_photo_person_id", table_name="face_embeddings"
        )
        op.drop_table("face_embeddings")

    if _has_table("person_embeddings") and "model_key" in _columns(
        "person_embeddings"
    ):
        op.drop_index(
            "ix_person_embeddings_model_key", table_name="person_embeddings"
        )
        with op.batch_alter_table("person_embeddings") as batch_op:
            batch_op.drop_column("model_key")
