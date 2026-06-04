"""イベント スキーマ。"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import ORMModel


class EventBase(BaseModel):
    name: str
    memo: str | None = None


class EventCreate(EventBase):
    pass


class EventUpdate(BaseModel):
    name: str | None = None
    memo: str | None = None


class EventOut(ORMModel):
    id: int
    name: str
    memo: str | None
    created_at: datetime
