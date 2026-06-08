"""外部API経由の顔判定リクエスト記録。

外部からの呼び出しは「判定のみ」（学習・人物登録は行わない）。受け取った画像は
写真ライブラリ(photos)とは別フォルダに WebP 変換して保存し、判定結果(JSON)と
ともに保持する。Webから閲覧・任意削除できる。
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class ApiQuery(Base, TimestampMixin):
    __tablename__ = "api_queries"

    id: Mapped[int] = mapped_column(primary_key=True)
    # api_storage_dir からの相対パス（WebPファイル名）
    path: Mapped[str] = mapped_column(String(1024), nullable=False)
    faces_detected: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # 判定結果: [{bbox, det_score, candidates:[{person_id,name,score,margin,model_key,matched}]}]
    result: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    # 呼び出し元の任意ラベル（外部システム識別用・任意）
    note: Mapped[str | None] = mapped_column(Text)
