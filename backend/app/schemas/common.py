"""共通スキーマ基底。"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    """ORM属性から構築可能な出力スキーマ基底。"""

    model_config = ConfigDict(from_attributes=True)
