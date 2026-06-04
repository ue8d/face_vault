"""設定 スキーマ。"""
from __future__ import annotations

from pydantic import BaseModel


class SettingItem(BaseModel):
    key: str
    label: str
    type: str  # str | int | float | secret
    group: str
    value: str  # secret は常に空（マスク）
    is_set: bool
    source: str  # db | env/default


class SettingsUpdate(BaseModel):
    # key -> 値（空文字/None で上書き解除しenv/デフォルトに戻す）
    values: dict[str, str | None]
