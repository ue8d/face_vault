"""定期収集スケジューラ。asyncio で全環境横断に due な収集元を巡回実行する。

main.py の lifespan で起動。30秒間隔で next_run_at 到来の有効ソースを処理。
多重起動防止: 実行開始時に next_run_at を前進させてから収集する。
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models.collect_source import CollectSource

logger = logging.getLogger(__name__)

_POLL_INTERVAL_SEC = 30


def _as_utc(value: datetime | None) -> datetime | None:
    """SQLite の DateTime は naive で返るため、aware な now と比較できるよう UTC 扱いに正規化。"""
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def due_sources(
    sources: list[CollectSource], now: datetime
) -> list[CollectSource]:
    """定期実行の対象（enabled・interval>=1・next_run_at<=now）を返す純粋関数。"""
    out: list[CollectSource] = []
    for s in sources:
        if not s.enabled or not s.interval_minutes or s.interval_minutes < 1:
            continue
        next_run = _as_utc(s.next_run_at)
        if next_run is None or next_run <= now:
            out.append(s)
    return out


def _run_due_once() -> int:
    """due なソースを1巡実行。処理件数を返す。独自セッションを使う。"""
    from app.db.base import SessionLocal
    from app.services.collector_service import CollectorService

    db = SessionLocal()
    processed = 0
    try:
        now = datetime.now(timezone.utc)
        sources = list(db.scalars(select(CollectSource)).all())
        targets = due_sources(sources, now)
        for source in targets:
            # 多重起動防止: 先に次回時刻を前進させてコミット
            source.next_run_at = now + timedelta(minutes=source.interval_minutes)
            db.commit()
            try:
                CollectorService(db, source.environment_id).run(source)
                processed += 1
            except Exception:  # noqa: BLE001 - 1ソース失敗で全体は止めない
                db.rollback()
                logger.warning("scheduled collect failed: source %s", source.id, exc_info=True)
    finally:
        db.close()
    return processed


async def collect_loop(stop: asyncio.Event) -> None:
    """停止イベントが立つまで _POLL_INTERVAL_SEC ごとに due 収集を実行。"""
    logger.info("collect scheduler started (poll=%ss)", _POLL_INTERVAL_SEC)
    while not stop.is_set():
        try:
            await asyncio.to_thread(_run_due_once)
        except Exception:  # noqa: BLE001 - スケジューラ自体は落とさない
            logger.warning("collect loop iteration failed", exc_info=True)
        try:
            await asyncio.wait_for(stop.wait(), timeout=_POLL_INTERVAL_SEC)
        except asyncio.TimeoutError:
            pass
    logger.info("collect scheduler stopped")
