"""Backfill optional face embeddings for already processed photos."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.face import embedding as emb
from app.face.embedder import FACE01, configure_runtime_embedders
from app.models.face_embedding import FaceEmbedding
from app.models.person_embedding import PersonEmbedding
from app.models.photo import Photo
from app.models.photo_person import PhotoPerson
from app.services.settings_service import SettingsService


@dataclass
class FaceBackfillResult:
    scanned: int = 0
    face_embeddings_created: int = 0
    person_embeddings_created: int = 0
    skipped: int = 0
    failed: int = 0


class FaceBackfillService:
    def __init__(
        self,
        db: Session,
        *,
        embedder=None,
        storage_dir: str | Path | None = None,
    ) -> None:
        self.db = db
        self.embedder = embedder
        self.storage = Path(storage_dir or get_settings().photo_storage_dir)

    def _get_embedder(self):
        if self.embedder is not None:
            return self.embedder

        cfg = SettingsService(self.db)
        enabled = bool(cfg.value("face01_enabled"))
        model_path = str(cfg.value("face01_model_path") or "")
        if not enabled:
            raise RuntimeError("face01 disabled")
        configure_runtime_embedders(
            face01_enabled=enabled, face01_model_path=model_path
        )

        from app.face.face01 import Face01Embedder

        self.embedder = Face01Embedder(model_path=model_path)
        return self.embedder

    @staticmethod
    def _parse_bbox(value: str | None) -> tuple[int, int, int, int] | None:
        if not value:
            return None
        try:
            x, y, w, h = (int(v) for v in value.split(","))
        except ValueError:
            return None
        if w <= 0 or h <= 0:
            return None
        return x, y, w, h

    def _has_face_embedding(self, link_id: int, model_key: str) -> bool:
        return (
            self.db.scalar(
                select(FaceEmbedding.id).where(
                    FaceEmbedding.photo_person_id == link_id,
                    FaceEmbedding.model_key == model_key,
                )
            )
            is not None
        )

    def _has_person_embedding(
        self, *, person_id: int, model_key: str, source_photo_id: int
    ) -> bool:
        return (
            self.db.scalar(
                select(PersonEmbedding.id).where(
                    PersonEmbedding.person_id == person_id,
                    PersonEmbedding.model_key == model_key,
                    PersonEmbedding.source_photo_id == source_photo_id,
                )
            )
            is not None
        )

    def backfill_face01(self, *, limit: int | None = None) -> FaceBackfillResult:
        import cv2

        face01 = self._get_embedder()
        _ = getattr(face01, "dim", None)
        result = FaceBackfillResult()
        stmt = (
            select(PhotoPerson, Photo)
            .join(Photo, PhotoPerson.photo_id == Photo.id)
            .order_by(PhotoPerson.id)
        )
        if limit is not None:
            stmt = stmt.limit(limit)

        for link, photo in self.db.execute(stmt).all():
            result.scanned += 1
            if self._has_face_embedding(link.id, FACE01):
                result.skipped += 1
                continue

            bbox = self._parse_bbox(link.bbox)
            fpath = self.storage / photo.path
            if bbox is None or not fpath.exists():
                result.failed += 1
                continue

            img = cv2.imread(str(fpath), cv2.IMREAD_COLOR)
            if img is None:
                result.failed += 1
                continue

            try:
                vec = np.asarray(face01.embed(img, bbox), dtype="float32")
            except Exception:
                result.failed += 1
                continue

            link.embeddings.append(
                FaceEmbedding(
                    model_key=FACE01,
                    embedding=emb.to_bytes(emb.l2_normalize(vec)),
                    dim=int(vec.shape[0]),
                )
            )
            result.face_embeddings_created += 1

            if link.person_id is not None and not self._has_person_embedding(
                person_id=link.person_id,
                model_key=FACE01,
                source_photo_id=photo.id,
            ):
                self.db.add(
                    PersonEmbedding(
                        person_id=link.person_id,
                        model_key=FACE01,
                        embedding=emb.to_bytes(emb.l2_normalize(vec)),
                        dim=int(vec.shape[0]),
                        source_photo_id=photo.id,
                    )
                )
                result.person_embeddings_created += 1

            self.db.flush()

        return result
