"""写真 サービス。アップロード保存 + メタ登録。

顔検出/Embedding/照合は FaceService（次フェーズ）に委譲。未導入環境では
スキップしてメタのみ登録 → ローカル動作確認可能。
"""
from __future__ import annotations

import io
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.photo import Photo
from app.repositories.photo import PhotoRepository
from app.schemas.photo import PhotoFilter, PhotoUpdate

settings = get_settings()
logger = logging.getLogger(__name__)


def _exif_taken_at(content: bytes) -> datetime | None:
    """画像EXIFから撮影日時を抽出（DateTimeOriginal→DateTime）。失敗時None。"""
    try:
        from PIL import Image

        img = Image.open(io.BytesIO(content))
        exif = img.getexif()
        if not exif:
            return None
        raw = exif.get_ifd(0x8769).get(36867)  # ExifIFD.DateTimeOriginal
        raw = raw or exif.get(306)  # 基本IFD.DateTime
        if not raw:
            return None
        dt = datetime.strptime(str(raw).strip(), "%Y:%m:%d %H:%M:%S")
        return dt.replace(tzinfo=timezone.utc)  # EXIFはtz無し → UTC扱い
    except Exception:  # noqa: BLE001 - EXIF無効でもアップロードは継続
        return None


class PhotoService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.photos = PhotoRepository(db)
        self.storage = Path(settings.photo_storage_dir)

    def search(self, f: PhotoFilter, *, limit: int = 100, offset: int = 0) -> list[Photo]:
        return self.photos.search(f, limit=limit, offset=offset)

    def get(self, photo_id: int) -> Photo | None:
        return self.photos.get(photo_id)

    def count(self) -> int:
        return self.photos.count()

    def update(self, photo: Photo, data: PhotoUpdate) -> Photo:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(photo, field, value)
        self.db.commit()
        self.db.refresh(photo)
        return photo

    def delete(self, photo: Photo) -> None:
        """写真を削除。実体ファイル・顔リンク・この画像由来のEmbedding・共起も整理。"""
        from sqlalchemy import delete as sql_delete
        from sqlalchemy import select

        from app.models.person_embedding import PersonEmbedding
        from app.models.photo_person import PhotoPerson
        from app.services.cooccurrence_service import CooccurrenceService

        # 共起を減算（割当済み人物のペア）
        person_ids = list(
            self.db.execute(
                select(PhotoPerson.person_id).where(
                    PhotoPerson.photo_id == photo.id, PhotoPerson.person_id.isnot(None)
                )
            ).scalars()
        )
        if person_ids:
            CooccurrenceService(self.db).bump_pairs(person_ids, delta=-1)

        # この画像から登録された参照ベクトルを除去（誤画像のベクトル汚染を防ぐ）
        emb_ids = list(
            self.db.execute(
                select(PersonEmbedding.id).where(PersonEmbedding.source_photo_id == photo.id)
            ).scalars()
        )
        if emb_ids:
            self.db.execute(
                sql_delete(PersonEmbedding).where(PersonEmbedding.id.in_(emb_ids))
            )

        fpath = self.storage / photo.path
        self.db.delete(photo)  # cascade で photo_persons 削除
        self.db.commit()

        try:
            fpath.unlink(missing_ok=True)
        except OSError:
            logger.warning("failed to remove file %s", fpath, exc_info=True)

        if emb_ids:  # ベクトルが減ったので索引再構築
            from app.face.registry import get_index
            from app.services.face_service import FaceService

            FaceService(self.db, get_index()).rebuild_index()

    def reprocess(self, photo: Photo) -> Photo:
        fpath = self.storage / photo.path
        if not fpath.exists():
            raise FileNotFoundError(photo.path)

        from app.face.registry import get_index
        from app.services.face_service import FaceService

        face_svc = FaceService(self.db, get_index())
        face_svc.rebuild_index()
        face_svc.reprocess_photo(photo, fpath.read_bytes())
        self.db.commit()
        self.db.refresh(photo)
        return photo

    def store_image(self, *, content: bytes, filename: str, memo: str | None = None) -> Photo:
        """画像をストレージに保存し photos 行を作成（顔処理は行わない）。

        参照顔登録など、顔は呼び出し側で明示的に扱うケース用。
        """
        self.storage.mkdir(parents=True, exist_ok=True)
        ext = Path(filename).suffix or ".jpg"
        rel = f"{uuid.uuid4().hex}{ext}"
        (self.storage / rel).write_bytes(content)
        photo = Photo(path=rel, memo=memo, taken_at=datetime.now(timezone.utc))
        self.photos.add(photo)
        self.db.commit()
        self.db.refresh(photo)
        return photo

    def save_upload(
        self,
        *,
        content: bytes,
        filename: str,
        memo: str | None = None,
        event_id: int | None = None,
        taken_at: datetime | None = None,
    ) -> Photo:
        self.storage.mkdir(parents=True, exist_ok=True)
        ext = Path(filename).suffix or ".jpg"
        rel = f"{uuid.uuid4().hex}{ext}"
        (self.storage / rel).write_bytes(content)

        photo = Photo(
            path=rel,
            memo=memo,
            event_id=event_id,
            # 明示指定 > EXIF撮影日時 > アップロード時刻
            taken_at=taken_at or _exif_taken_at(content) or datetime.now(timezone.utc),
        )
        self.photos.add(photo)
        self.db.commit()  # メタを先に確定
        self.db.refresh(photo)

        # 顔検出→Embedding→照合→photo_persons登録（best-effort・別トランザクション）。
        # ランタイム未導入・モデルDL失敗・デコード不能等でもアップロード自体は成功済み。
        try:
            from app.face.registry import get_index
            from app.services.face_service import FaceService

            FaceService(self.db, get_index()).process_photo(photo, content)
            self.db.commit()
        except Exception:  # noqa: BLE001 - 顔処理は付随処理。失敗してもメタ登録は維持
            self.db.rollback()
            logger.warning("face processing skipped for photo %s", photo.id, exc_info=True)

        self.db.refresh(photo)
        return photo
