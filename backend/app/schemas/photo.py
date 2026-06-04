"""写真 スキーマ。"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, HttpUrl

from app.schemas.common import ORMModel


class PhotoPersonOut(ORMModel):
    id: int
    person_id: int | None
    person_name: str | None = None
    confidence: float | None
    bbox: str | None


class PhotoOut(ORMModel):
    id: int
    path: str
    taken_at: datetime | None
    memo: str | None
    event_id: int | None
    created_at: datetime
    person_links: list[PhotoPersonOut] = []


class PhotoUpdate(BaseModel):
    taken_at: datetime | None = None
    memo: str | None = None
    event_id: int | None = None


class PhotoUrlImport(BaseModel):
    url: HttpUrl
    taken_at: datetime | None = None
    memo: str | None = None
    event_id: int | None = None


class PhotoUrlsImport(BaseModel):
    urls: list[HttpUrl]
    taken_at: datetime | None = None
    memo: str | None = None
    event_id: int | None = None


class PhotoImportError(BaseModel):
    source: str
    detail: str


class PhotoBulkImportResult(BaseModel):
    created: list[PhotoOut]
    errors: list[PhotoImportError] = []


class PhotoFilter(BaseModel):
    """写真検索条件。"""

    person_id: int | None = None
    event_id: int | None = None
    event_name: str | None = None
    tag: str | None = None
    year: int | None = None
    month: int | None = None
