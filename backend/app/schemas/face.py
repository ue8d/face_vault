"""顔関連 スキーマ。"""
from __future__ import annotations

from pydantic import BaseModel

from app.schemas.common import ORMModel


class CandidateOut(BaseModel):
    person_id: int
    score: float


class ConfirmFaceRequest(BaseModel):
    person_id: int


class PhotoPersonOut(ORMModel):
    id: int
    photo_id: int
    person_id: int | None
    confidence: float | None
    bbox: str | None


class ReindexResponse(BaseModel):
    backend: str
    size: int
