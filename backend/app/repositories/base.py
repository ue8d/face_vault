"""汎用リポジトリ基底。env_id 指定時は environment_id を持つモデルを自動スコープ。"""
from __future__ import annotations

from typing import Generic, TypeVar

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    model: type[ModelT]

    def __init__(self, db: Session, env_id: int | None = None) -> None:
        self.db = db
        self.env_id = env_id

    def _scoped(self, stmt: Select) -> Select:
        if self.env_id is not None and hasattr(self.model, "environment_id"):
            stmt = stmt.where(self.model.environment_id == self.env_id)
        return stmt

    def get(self, id_: int) -> ModelT | None:
        obj = self.db.get(self.model, id_)
        if (
            obj is not None
            and self.env_id is not None
            and getattr(obj, "environment_id", self.env_id) != self.env_id
        ):
            return None  # 他環境のリソースは不可視
        return obj

    def count(self) -> int:
        stmt = self._scoped(select(func.count()).select_from(self.model))
        return int(self.db.scalar(stmt) or 0)

    def list(self, *, limit: int = 100, offset: int = 0) -> list[ModelT]:
        stmt = self._scoped(select(self.model)).limit(limit).offset(offset)
        return list(self.db.scalars(stmt).all())

    def add(self, obj: ModelT) -> ModelT:
        if self.env_id is not None and hasattr(obj, "environment_id"):
            obj.environment_id = self.env_id
        self.db.add(obj)
        self.db.flush()
        return obj

    def delete(self, obj: ModelT) -> None:
        self.db.delete(obj)
        self.db.flush()
