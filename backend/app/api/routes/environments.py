"""環境（テナント）エンドポイント。設定画面から追加/改名/削除。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.schemas.environment import EnvironmentCreate, EnvironmentOut, EnvironmentUpdate
from app.services.environment_service import EnvironmentService, ensure_default_environment

router = APIRouter()


def _service(db: Session = Depends(get_db)) -> EnvironmentService:
    return EnvironmentService(db)


@router.get("/environments", response_model=list[EnvironmentOut])
def list_environments(svc: EnvironmentService = Depends(_service)):
    ensure_default_environment(svc.db)
    return svc.list()


@router.post(
    "/environments", response_model=EnvironmentOut, status_code=status.HTTP_201_CREATED
)
def create_environment(data: EnvironmentCreate, svc: EnvironmentService = Depends(_service)):
    try:
        return svc.create(data.name)
    except ValueError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from e


@router.patch("/environments/{env_id}", response_model=EnvironmentOut)
def rename_environment(
    env_id: int, data: EnvironmentUpdate, svc: EnvironmentService = Depends(_service)
):
    env = svc.get(env_id)
    if env is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "environment not found")
    try:
        return svc.rename(env, data.name)
    except ValueError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from e


@router.delete("/environments/{env_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_environment(env_id: int, svc: EnvironmentService = Depends(_service)) -> Response:
    """環境と配下の全データ（人物/写真/イベント/タグ/APIログ + ファイル実体）を削除。"""
    env = svc.get(env_id)
    if env is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "environment not found")
    try:
        svc.delete(env)
    except ValueError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from e
    return Response(status_code=status.HTTP_204_NO_CONTENT)
