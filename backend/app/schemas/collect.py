"""収集元 I/O スキーマ。"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.collect_source import CRAWL_MODES


class CollectSourceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    start_url: str = Field(min_length=1)
    crawl_mode: str = "page"
    max_pages: int = Field(default=20, ge=1, le=1000)
    max_images: int = Field(default=100, ge=1, le=10000)
    same_domain_only: bool = True
    respect_robots: bool = True
    enabled: bool = True
    interval_minutes: int = Field(default=0, ge=0)  # 0=手動のみ / >=1=分間隔

    @field_validator("crawl_mode")
    @classmethod
    def _check_mode(cls, v: str) -> str:
        if v not in CRAWL_MODES:
            raise ValueError(f"crawl_mode must be one of {CRAWL_MODES}")
        return v

    @field_validator("start_url")
    @classmethod
    def _check_url(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("start_url must be http(s)")
        return v


class CollectSourceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    start_url: str | None = None
    crawl_mode: str | None = None
    max_pages: int | None = Field(default=None, ge=1, le=1000)
    max_images: int | None = Field(default=None, ge=1, le=10000)
    same_domain_only: bool | None = None
    respect_robots: bool | None = None
    enabled: bool | None = None
    interval_minutes: int | None = Field(default=None, ge=0)

    @field_validator("crawl_mode")
    @classmethod
    def _check_mode(cls, v: str | None) -> str | None:
        if v is not None and v not in CRAWL_MODES:
            raise ValueError(f"crawl_mode must be one of {CRAWL_MODES}")
        return v

    @field_validator("start_url")
    @classmethod
    def _check_url(cls, v: str | None) -> str | None:
        if v is not None and not v.startswith(("http://", "https://")):
            raise ValueError("start_url must be http(s)")
        return v


class CollectSourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    start_url: str
    crawl_mode: str
    max_pages: int
    max_images: int
    same_domain_only: bool
    respect_robots: bool
    enabled: bool
    interval_minutes: int
    last_run_at: datetime | None
    next_run_at: datetime | None
    last_status: str | None
    last_error: str | None
    created_at: datetime


class CollectRunResult(BaseModel):
    found_urls: int
    new_urls: int
    saved: int
    skipped_duplicate: int
    failed: int
    pages_scanned: int
    error: str | None = None
