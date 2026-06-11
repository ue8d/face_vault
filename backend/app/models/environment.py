"""環境（テナント）モデル。人物/写真/イベント/タグ/API受信ログを完全分離する単位。

A環境に登録した人物はB環境からは見えない。FAISS index も環境別。
削除時は配下データを EnvironmentService が明示削除（ファイル実体含む）。
"""
from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin

DEFAULT_ENVIRONMENT_ID = 1
DEFAULT_ENVIRONMENT_NAME = "default"


class Environment(Base, TimestampMixin):
    __tablename__ = "environments"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
