"""自動画像収集元（クロール対象）。環境ごとに登録し、手動/定期で巡回する。

収集した画像は写真ライブラリに保存され、顔は未照合のまま確認キューへ出る
（新規人物の自動作成はしない）。crawl_mode で巡回範囲を切り替える。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.models.environment import DEFAULT_ENVIRONMENT_ID

# crawl_mode
PAGE = "page"  # start_url のページ内画像のみ
SHALLOW = "shallow"  # 同一ドメインのリンクを1階層辿る
DOMAIN = "domain"  # 同一ドメインを BFS 巡回
CRAWL_MODES = (PAGE, SHALLOW, DOMAIN)


class CollectSource(Base, TimestampMixin):
    __tablename__ = "collect_sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    environment_id: Mapped[int] = mapped_column(
        ForeignKey("environments.id", ondelete="CASCADE"),
        default=DEFAULT_ENVIRONMENT_ID,
        server_default=str(DEFAULT_ENVIRONMENT_ID),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    start_url: Mapped[str] = mapped_column(Text, nullable=False)
    crawl_mode: Mapped[str] = mapped_column(
        String(16), default=PAGE, server_default=PAGE, nullable=False
    )
    max_pages: Mapped[int] = mapped_column(
        Integer, default=20, server_default="20", nullable=False
    )
    max_images: Mapped[int] = mapped_column(
        Integer, default=100, server_default="100", nullable=False
    )
    same_domain_only: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="1", nullable=False
    )
    respect_robots: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="1", nullable=False
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="1", nullable=False
    )
    # 0 = 手動のみ / >=1 = 分間隔の定期巡回（下限1分）
    interval_minutes: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_status: Mapped[str | None] = mapped_column(String(16))  # ok | error | running
    last_error: Mapped[str | None] = mapped_column(Text)
