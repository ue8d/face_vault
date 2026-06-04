"""確認キュー / 統合候補 スキーマ。"""
from __future__ import annotations

from pydantic import BaseModel


class CandidateOut(BaseModel):
    person_id: int
    name: str
    score: float


class ReviewItemOut(BaseModel):
    link_id: int
    photo_id: int
    bbox: str | None
    confidence: float | None
    person_id: int | None
    person_name: str | None
    candidates: list[CandidateOut] = []


class ReviewCountOut(BaseModel):
    count: int


class MergeSuggestionOut(BaseModel):
    person_a_id: int
    person_a_name: str
    person_a_photo_id: int | None = None
    person_a_link_id: int | None = None
    person_b_id: int
    person_b_name: str
    person_b_photo_id: int | None = None
    person_b_link_id: int | None = None
    score: float


class DismissRequest(BaseModel):
    person_a_id: int
    person_b_id: int
