"""人物 スキーマ。"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel
from app.schemas.tag import TagOut


class PersonBase(BaseModel):
    name: str
    relation: str | None = None
    memo: str | None = None


class PersonCreate(PersonBase):
    nicknames: list[str] = []  # 複数可
    tags: list[str] = []  # タグ名。無ければ作成


class PersonUpdate(BaseModel):
    name: str | None = None
    relation: str | None = None
    memo: str | None = None
    nicknames: list[str] | None = None
    tags: list[str] | None = None


class PersonImportResult(BaseModel):
    created: int = 0
    updated: int = 0
    skipped: int = 0
    face_queued: int = 0  # img_url から参照顔取得を予約した件数
    errors: list[str] = Field(default_factory=list)


class FaceImportStatus(BaseModel):
    pending: int = 0
    done: int = 0
    failed: int = 0


class PersonOut(ORMModel):
    id: int
    name: str
    nicknames: list[str] = []
    relation: str | None
    memo: str | None
    created_at: datetime
    tags: list[TagOut] = []

    @field_validator("nicknames", mode="before")
    @classmethod
    def _to_names(cls, v: object) -> list[str]:
        if not v:
            return []
        return [x if isinstance(x, str) else x.name for x in v]  # type: ignore[union-attr]
