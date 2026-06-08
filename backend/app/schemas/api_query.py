"""外部API顔判定 スキーマ。"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import ORMModel


class ApiCandidate(BaseModel):
    person_id: int
    name: str
    score: float
    margin: float
    model_key: str
    matched: bool


class ApiFaceResult(BaseModel):
    bbox: list[int]
    det_score: float
    candidates: list[ApiCandidate] = []


class ApiQueryOut(ORMModel):
    id: int
    path: str
    faces_detected: int
    result: list[ApiFaceResult] = []
    note: str | None = None
    created_at: datetime


class ApiIdentifyResponse(BaseModel):
    """外部呼び出しへの判定レスポンス。"""

    query_id: int
    faces_detected: int
    result: list[ApiFaceResult] = []
