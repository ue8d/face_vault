"""設定エンドポイント。DB管理の動的設定を Web から閲覧/更新。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.schemas.setting import SettingItem, SettingsUpdate
from app.services.settings_service import SettingsService

router = APIRouter()


@router.get("/settings", response_model=list[SettingItem])
def list_settings(db: Session = Depends(get_db)):
    """編集可能な設定一覧（実効値・出所付き、secretはマスク）。"""
    return SettingsService(db).all_items()


@router.put("/settings", response_model=list[SettingItem])
def update_settings(body: SettingsUpdate, db: Session = Depends(get_db)):
    """部分更新。空値はDB上書きを削除しenv/デフォルトへ戻す。"""
    svc = SettingsService(db)
    svc.update(body.values)
    return svc.all_items()
