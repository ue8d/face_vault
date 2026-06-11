"""API 共通依存性。環境（テナント）解決。

X-Environment-Id ヘッダで対象環境を指定。未指定時は最初の環境
（無ければ default を自動作成）。存在しない環境IDは 404。
"""
from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.models.environment import Environment
from app.services.environment_service import ensure_default_environment


def get_env_id(
    x_environment_id: str | None = Header(default=None, alias="X-Environment-Id"),
    db: Session = Depends(get_db),
) -> int:
    if x_environment_id is None or str(x_environment_id).strip() == "":
        return ensure_default_environment(db).id
    try:
        env_id = int(x_environment_id)
    except ValueError as e:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "X-Environment-Id must be an integer"
        ) from e
    if db.get(Environment, env_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "environment not found")
    return env_id
