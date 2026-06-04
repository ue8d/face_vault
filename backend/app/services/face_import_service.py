"""顔画像取込キューの処理。img_url を取得→顔検出→参照顔登録。

CSV取込(大量)を非同期化するため、取込はキュー登録のみ。実取得はこのサービスが
バッチで処理（バックグラウンドタスク or 明示エンドポイントから）。
"""
from __future__ import annotations

import logging
import urllib.request
from urllib.parse import quote, urlsplit, urlunsplit

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.face.registry import get_index
from app.models.face_import import FaceImport
from app.services.face_service import FaceService
from app.services.photo_service import PhotoService

logger = logging.getLogger(__name__)

_MAX_BYTES = 20 * 1024 * 1024  # 20MB
_TIMEOUT = 20


def _encode_url(url: str) -> str:
    """非ASCII（日本語ファイル名等）を含むURLを percent-encode。"""
    p = urlsplit(url.strip())
    return urlunsplit(
        (p.scheme, p.netloc, quote(p.path), quote(p.query, safe="=&?"), p.fragment)
    )


def _download(url: str) -> bytes:
    req = urllib.request.Request(_encode_url(url), headers={"User-Agent": "face_vault/1.0"})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        data = resp.read(_MAX_BYTES + 1)
    if len(data) > _MAX_BYTES:
        raise ValueError("画像が大きすぎます")
    if not data:
        raise ValueError("空の応答")
    return data


class FaceImportService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def status(self) -> dict[str, int]:
        rows = self.db.execute(
            select(FaceImport.status, func.count(FaceImport.id)).group_by(FaceImport.status)
        ).all()
        out = {"pending": 0, "done": 0, "failed": 0}
        for st, n in rows:
            out[st] = n
        return out

    def process_batch(self, *, limit: int = 25) -> dict[str, int]:
        """pending を limit 件処理。各件: 取得→検出→参照顔登録。"""
        from app.face.detector import get_detector

        face = FaceService(self.db, get_index())
        photos = PhotoService(self.db)
        rows = self.db.execute(
            select(FaceImport).where(FaceImport.status == "pending").limit(limit)
        ).scalars().all()

        done = failed = 0
        for row in rows:
            try:
                content = _download(row.img_url)
                faces = get_detector().detect(content)
                if not faces:
                    raise ValueError("顔が検出できません")
                if not face.quality_ok(faces[0]):
                    raise ValueError("顔の品質が低い（小さい/不鮮明）")
                photo = photos.store_image(
                    content=content,
                    filename="import.jpg",
                    memo=f"CSV取込 参照顔 (person #{row.person_id})",
                )
                face.register_reference(row.person_id, faces[0], photo.id)
                row.status = "done"
                row.error = None
                done += 1
            except Exception as e:  # noqa: BLE001 - 1件失敗で全体は止めない
                row.status = "failed"
                row.error = str(e)[:500]
                failed += 1
            self.db.commit()
        return {"processed": done + failed, "done": done, "failed": failed}

    def retry_failed(self) -> int:
        """failed を pending に戻す。"""
        rows = self.db.execute(
            select(FaceImport).where(FaceImport.status == "failed")
        ).scalars().all()
        for r in rows:
            r.status = "pending"
            r.error = None
        self.db.commit()
        return len(rows)


def drain_all(*, batch: int = 25, max_batches: int = 100000) -> None:
    """キューを空になるまで処理（バックグラウンドタスク用）。独自セッションを使う。"""
    from app.db.base import SessionLocal

    db = SessionLocal()
    try:
        svc = FaceImportService(db)
        for _ in range(max_batches):
            if svc.status()["pending"] == 0:
                break
            r = svc.process_batch(limit=batch)
            if r["processed"] == 0:
                break
        logger.info("face import drained: %s", svc.status())
    finally:
        db.close()
