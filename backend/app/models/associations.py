"""多対多 中間テーブル（属性なし）。属性ありは独立モデル化。"""
from __future__ import annotations

from sqlalchemy import Column, ForeignKey, Integer, Table

from app.db.base import Base

# 人物 ↔ タグ
person_tags = Table(
    "person_tags",
    Base.metadata,
    Column("person_id", Integer, ForeignKey("persons.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)

# イベント ↔ 人物
event_persons = Table(
    "event_persons",
    Base.metadata,
    Column("event_id", Integer, ForeignKey("events.id", ondelete="CASCADE"), primary_key=True),
    Column("person_id", Integer, ForeignKey("persons.id", ondelete="CASCADE"), primary_key=True),
)
