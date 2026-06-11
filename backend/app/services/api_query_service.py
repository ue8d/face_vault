"""外部API顔判定サービス。

外部からの画像を「判定のみ」で処理する（学習・人物登録・photo_persons は作らない）。
判定は FaceService.match() を再利用（DBへの書き込みなし）。受け取った画像は
api_storage_dir へ WebP 変換して保存し、結果を api_queries に記録する。
"""
from __future__ import annotations

import io
import logging
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.api_query import ApiQuery
from app.models.person import Person

settings = get_settings()
logger = logging.getLogger(__name__)


def _to_webp(content: bytes) -> tuple[bytes, str]:
    """画像を WebP に変換して返す。変換不能なら元バイト+拡張子フォールバック。"""
    try:
        from PIL import Image

        img = Image.open(io.BytesIO(content))
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="WEBP", quality=82, method=4)
        return buf.getvalue(), ".webp"
    except Exception:  # noqa: BLE001 - PIL未導入・デコード不能でも保存自体は継続
        logger.warning("webp変換に失敗。元データで保存", exc_info=True)
        return content, ".bin"


class ApiQueryService:
    def __init__(self, db: Session, env_id: int | None = None) -> None:
        from app.services.settings_service import SettingsService

        self.db = db
        self.env_id = env_id
        # DB設定(api_storage_dir)を尊重。未設定なら env/デフォルトへフォールバック。
        storage_dir = SettingsService(db).value("api_storage_dir") or settings.api_storage_dir
        self.storage = Path(storage_dir)

    # --- 判定（学習なし） ---
    def identify(
        self, *, content: bytes, note: str | None = None, top_n: int = 5
    ) -> ApiQuery:
        """画像から顔検出 → 既存人物と照合（書き込みなし）→ 画像保存 + 記録。

        検出器が必要。ランタイム未導入時は ImportError を送出（呼び出し側で503）。
        """
        from app.face.detector import get_detector
        from app.face.registry import get_index
        from app.services.face_service import FaceService

        faces = get_detector().detect(content)

        face_svc = FaceService(
            self.db, get_index(env_id=self.env_id), env_id=self.env_id
        )
        results: list[dict[str, Any]] = []
        for f in faces:
            cands = face_svc.match(f.embeddings, k=max(1, top_n))[:top_n]
            names = self._names_for([c.person_id for c in cands])
            x, y, w, h = f.bbox
            results.append(
                {
                    "bbox": [int(x), int(y), int(w), int(h)],
                    "det_score": float(getattr(f, "det_score", 0.0)),
                    "candidates": [
                        {
                            "person_id": c.person_id,
                            "name": names.get(c.person_id, f"#{c.person_id}"),
                            "score": round(float(c.score), 4),
                            "margin": round(float(c.margin), 4),
                            "model_key": c.model_key,
                            "matched": c.margin >= 0,
                        }
                        for c in cands
                    ],
                }
            )

        webp, ext = _to_webp(content)
        self.storage.mkdir(parents=True, exist_ok=True)
        rel = f"{uuid.uuid4().hex}{ext}"
        (self.storage / rel).write_bytes(webp)

        row = ApiQuery(
            path=rel,
            faces_detected=len(faces),
            result=results,
            note=note,
        )
        if self.env_id is not None:
            row.environment_id = self.env_id
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    # --- 学習（Web確認 → 人物代表ベクトルへ登録） ---
    def learn(self, row: ApiQuery, *, person_id: int, face_index: int = 0) -> ApiQuery:
        """受信画像の指定顔を person_id の代表ベクトルとして学習する。

        画像を再検出し、result と同順の face_index の顔を登録（DBに人物ベクトル追加）。
        検出器が必要（未導入時 ImportError → 呼び出し側で503）。
        """
        from app.face.detector import get_detector
        from app.face.registry import get_index
        from app.services.face_service import FaceService

        person = self.db.get(Person, person_id)
        # 学習先は受信ログと同じ環境の人物に限定（環境間のベクトル汚染防止）
        if person is None or person.environment_id != row.environment_id:
            raise LookupError("person not found")

        fpath = self.file_path(row)
        if not fpath.exists():
            raise FileNotFoundError(row.path)

        faces = get_detector().detect(fpath.read_bytes())
        if not faces or face_index < 0 or face_index >= len(faces):
            raise ValueError("face not found")

        FaceService(
            self.db,
            get_index(env_id=row.environment_id),
            env_id=row.environment_id,
        ).learn_face(person_id, faces[face_index])
        row.learned_person_id = person_id
        self.db.commit()
        self.db.refresh(row)
        self._attach_learned_name(row)
        return row

    def _attach_learned_name(self, row: ApiQuery) -> None:
        if row.learned_person_id is None:
            row.learned_person_name = None  # type: ignore[attr-defined]
            return
        name = self._names_for([row.learned_person_id]).get(row.learned_person_id)
        row.learned_person_name = name  # type: ignore[attr-defined]

    def _names_for(self, person_ids: list[int]) -> dict[int, str]:
        ids = [pid for pid in set(person_ids) if pid is not None]
        if not ids:
            return {}
        rows = self.db.execute(
            select(Person.id, Person.name).where(Person.id.in_(ids))
        ).all()
        return {pid: name for pid, name in rows}

    # --- 閲覧 / 管理 ---
    def list(self, *, limit: int = 100, offset: int = 0) -> list[ApiQuery]:
        stmt = select(ApiQuery)
        if self.env_id is not None:
            stmt = stmt.where(ApiQuery.environment_id == self.env_id)
        stmt = (
            stmt.order_by(ApiQuery.created_at.desc(), ApiQuery.id.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = list(self.db.scalars(stmt).all())
        names = self._names_for([r.learned_person_id for r in rows if r.learned_person_id])
        for r in rows:
            r.learned_person_name = (  # type: ignore[attr-defined]
                names.get(r.learned_person_id) if r.learned_person_id else None
            )
        return rows

    def get(self, query_id: int) -> ApiQuery | None:
        row = self.db.get(ApiQuery, query_id)
        if row is not None:
            self._attach_learned_name(row)
        return row

    def file_path(self, row: ApiQuery) -> Path:
        return self.storage / row.path

    def delete(self, row: ApiQuery) -> None:
        fpath = self.file_path(row)
        self.db.delete(row)
        self.db.commit()
        try:
            fpath.unlink(missing_ok=True)
        except OSError:
            logger.warning("failed to remove api image %s", fpath, exc_info=True)
