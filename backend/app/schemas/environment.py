"""環境 I/O スキーマ。"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EnvironmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class EnvironmentUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class EnvironmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    created_at: datetime
    person_count: int = 0
    photo_count: int = 0
