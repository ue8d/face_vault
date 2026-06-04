"""タグ スキーマ。"""
from __future__ import annotations

from app.schemas.common import ORMModel


class TagOut(ORMModel):
    id: int
    name: str
