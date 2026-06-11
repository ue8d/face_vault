"""自動画像収集 エンドポイント。収集元の CRUD と手動実行。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_env_id
from app.db.base import get_db
from app.models.collect_source import CollectSource
from app.schemas.collect import (
    CollectRunResult,
    CollectSourceCreate,
    CollectSourceOut,
    CollectSourceUpdate,
)
from app.services.collector_service import CollectorService

router = APIRouter()


def _get_source(db: Session, env_id: int, source_id: int) -> CollectSource:
    src = db.get(CollectSource, source_id)
    if src is None or src.environment_id != env_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "collect source not found")
    return src


@router.get("/collect/sources", response_model=list[CollectSourceOut])
def list_sources(db: Session = Depends(get_db), env_id: int = Depends(get_env_id)):
    rows = db.scalars(
        select(CollectSource)
        .where(CollectSource.environment_id == env_id)
        .order_by(CollectSource.id)
    ).all()
    return list(rows)


@router.post(
    "/collect/sources",
    response_model=CollectSourceOut,
    status_code=status.HTTP_201_CREATED,
)
def create_source(
    data: CollectSourceCreate,
    db: Session = Depends(get_db),
    env_id: int = Depends(get_env_id),
):
    src = CollectSource(environment_id=env_id, **data.model_dump())
    db.add(src)
    db.commit()
    db.refresh(src)
    return src


@router.patch("/collect/sources/{source_id}", response_model=CollectSourceOut)
def update_source(
    source_id: int,
    data: CollectSourceUpdate,
    db: Session = Depends(get_db),
    env_id: int = Depends(get_env_id),
):
    src = _get_source(db, env_id, source_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(src, field, value)
    db.commit()
    db.refresh(src)
    return src


@router.delete("/collect/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_source(
    source_id: int,
    db: Session = Depends(get_db),
    env_id: int = Depends(get_env_id),
) -> Response:
    src = _get_source(db, env_id, source_id)
    db.delete(src)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/collect/sources/{source_id}/run", response_model=CollectRunResult)
def run_source(
    source_id: int,
    db: Session = Depends(get_db),
    env_id: int = Depends(get_env_id),
):
    """収集元を今すぐ1回巡回（同期）。収集件数を返す。

    crawl_mode=domain は時間がかかる場合あり。収集画像は確認キューに入る。
    """
    src = _get_source(db, env_id, source_id)
    result = CollectorService(db, env_id).run(src)
    return CollectRunResult(**result.__dict__)
