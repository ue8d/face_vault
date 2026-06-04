"""顔処理サービス。検出顔の照合・人物Embedding登録・写真処理。

VectorIndex(FAISS/numpy) と FaceDetector を注入可能 → テスト容易。
index id 空間 = person_embeddings.id。検索結果を person_id に解決し集約。
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.face import embedding as emb
from app.face.detector import DetectedFace, FaceDetector
from app.face.index import VectorIndex
from app.models.person_embedding import PersonEmbedding
from app.models.photo import Photo
from app.models.photo_person import PhotoPerson
from app.services.cooccurrence_service import CooccurrenceService

settings = get_settings()


@dataclass
class Candidate:
    person_id: int
    score: float  # コサイン類似（高いほど同一人物）


class FaceService:
    def __init__(
        self,
        db: Session,
        index: VectorIndex,
        detector: FaceDetector | None = None,
        *,
        threshold: float | None = None,
    ) -> None:
        self.db = db
        self.index = index
        self._detector = detector
        from app.services.settings_service import SettingsService

        cfg = SettingsService(db)
        if threshold is not None:
            self.threshold = threshold
        else:
            self.threshold = float(cfg.value("match_threshold") or 0.35)
        self.min_det_score = float(cfg.value("face_min_det_score") or 0.0)
        self.min_px = int(cfg.value("face_min_px") or 0)

    def quality_ok(self, f: DetectedFace) -> bool:
        """参照ベクトル登録に足る品質か（検出信頼度・顔サイズ）。"""
        _, _, w, h = f.bbox
        return f.det_score >= self.min_det_score and max(w, h) >= self.min_px

    # --- インデックス構築 ---
    def rebuild_index(self) -> int:
        rows = self.db.execute(
            select(PersonEmbedding.id, PersonEmbedding.embedding)
        ).all()
        self.index.build([(rid, emb.from_bytes(buf)) for rid, buf in rows])
        return self.index.size

    # --- 人物Embedding登録 ---
    def register_embedding(
        self, person_id: int, vec: np.ndarray, *, source_photo_id: int | None = None
    ) -> PersonEmbedding:
        row = PersonEmbedding(
            person_id=person_id,
            embedding=emb.to_bytes(emb.l2_normalize(vec)),
            dim=int(vec.shape[0]),
            source_photo_id=source_photo_id,
        )
        self.db.add(row)
        self.db.flush()
        self.index.add(row.id, vec)
        return row

    # --- 照合 ---
    def match(self, vec: np.ndarray, *, k: int = 5) -> list[Candidate]:
        """検出顔ベクトルに近い人物候補を類似降順で。person単位に集約。"""
        hits = self.index.search(vec, k=k)
        if not hits:
            return []
        ids = [eid for eid, _ in hits]
        emb_to_person = dict(
            self.db.execute(
                select(PersonEmbedding.id, PersonEmbedding.person_id).where(
                    PersonEmbedding.id.in_(ids)
                )
            ).all()
        )
        best: dict[int, float] = {}
        for eid, score in hits:
            pid = emb_to_person.get(eid)
            if pid is None:
                continue
            if pid not in best or score > best[pid]:
                best[pid] = score
        cands = [Candidate(person_id=p, score=s) for p, s in best.items()]
        cands.sort(key=lambda c: c.score, reverse=True)
        return cands

    # --- 写真処理（検出済みfacesから） ---
    def process_detections(
        self, photo: Photo, faces: list[DetectedFace], *, auto_enroll: bool | None = None
    ) -> list[PhotoPerson]:
        """検出顔を照合 → photo_persons 登録。

        - 閾値超: 既存人物に紐付け
        - 未一致 & auto_enroll: 新規人物を自動作成しEmbedding登録（次回から照合対象）
        - 未一致 & not auto_enroll: person_id=None（未照合のまま手動確定待ち）
        """
        if auto_enroll is None:
            from app.services.settings_service import SettingsService

            auto_enroll = bool(SettingsService(self.db).value("auto_enroll_faces"))

        links: list[PhotoPerson] = []
        used: set[int] = set()  # 同一写真内で同一人物への重複リンク防止（uq_photo_person）
        # 各顔の最良候補を先に算出し、信頼度の高い順に確定（重複時は高スコア側を残す）
        scored = [(f, (self.match(f.embedding, k=1) or [None])[0]) for f in faces]
        scored.sort(key=lambda t: t[1].score if t[1] else -1.0, reverse=True)
        for f, top in scored:
            matched = top.person_id if top and top.score >= self.threshold else None

            if matched is not None and matched in used:
                matched = None  # 既に同写真で使用済み → 未照合化（自動登録もしない）
            elif matched is None and auto_enroll and self.quality_ok(f):
                # 品質ゲート通過時のみ自動登録（低品質は未照合のまま確認キューへ）
                matched = self._auto_create_person(f, source_photo_id=photo.id)

            if matched is not None:
                used.add(matched)

            x, y, w, h = f.bbox
            link = PhotoPerson(
                photo_id=photo.id,
                person_id=matched,
                confidence=top.score if top else None,
                embedding=emb.to_bytes(emb.l2_normalize(f.embedding)),
                bbox=f"{x},{y},{w},{h}",
            )
            self.db.add(link)
            links.append(link)
        self.db.flush()

        person_ids = [link.person_id for link in links if link.person_id is not None]
        CooccurrenceService(self.db).bump_pairs(person_ids)
        return links

    def _auto_create_person(self, f: DetectedFace, *, source_photo_id: int) -> int:
        """未一致顔から新規人物を自動作成し、Embeddingを登録。person_id を返す。"""
        from app.models.person import Person

        person = Person(name="（自動登録）", memo="顔認識による自動登録。確認/改名/統合してください。")
        self.db.add(person)
        self.db.flush()
        person.name = f"未確認人物 #{person.id}"
        self.register_embedding(person.id, f.embedding, source_photo_id=source_photo_id)
        return person.id

    # --- 参照顔登録（保存済み写真の顔を人物代表として登録） ---
    def register_reference(
        self, person_id: int, face: DetectedFace, photo_id: int
    ) -> PersonEmbedding:
        """検出顔を人物の代表Embeddingとして登録し、写真リンクも作成。

        元画像(photo_id)に紐付くため、参照写真が本人の写真一覧に確定状態で出る。
        """
        row = self.register_embedding(person_id, face.embedding, source_photo_id=photo_id)
        x, y, w, h = face.bbox
        link = PhotoPerson(
            photo_id=photo_id,
            person_id=person_id,
            confidence=1.0,
            embedding=emb.to_bytes(emb.l2_normalize(face.embedding)),
            bbox=f"{x},{y},{w},{h}",
        )
        self.db.add(link)
        self.db.flush()
        return row

    # --- 手動確定（候補→人物紐付け） ---
    def confirm_face(self, link: PhotoPerson, person_id: int) -> PhotoPerson:
        """検出顔を人物に確定。その顔Embeddingを人物代表として登録 + 共起更新。"""
        if link.person_id == person_id:
            link.confidence = 1.0
            self.db.commit()
            return link
        # 同一写真に同一人物が既に割当済みなら重複(uq_photo_person)になる
        dup = self.db.scalar(
            select(PhotoPerson.id).where(
                PhotoPerson.photo_id == link.photo_id,
                PhotoPerson.person_id == person_id,
                PhotoPerson.id != link.id,
            )
        )
        if dup is not None:
            raise ValueError("この写真には既にこの人物が割り当てられています")
        link.person_id = person_id
        link.confidence = 1.0  # 手動確定済み → 確認キューから除外
        self.db.flush()
        if link.embedding:
            self.register_embedding(
                person_id, emb.from_bytes(link.embedding), source_photo_id=link.photo_id
            )
        # 新確定人物 と 同写真の既存確定人物 の新規ペアのみ共起+1（重複計上回避）
        others = self.db.execute(
            select(PhotoPerson.person_id).where(
                PhotoPerson.photo_id == link.photo_id,
                PhotoPerson.person_id.isnot(None),
                PhotoPerson.person_id != person_id,
                PhotoPerson.id != link.id,
            )
        ).scalars().all()
        cooc = CooccurrenceService(self.db)
        for other in set(others):
            cooc.bump_pairs([person_id, other])
        self.db.commit()
        return link

    def process_photo(self, photo: Photo, image_bytes: bytes) -> list[PhotoPerson]:
        """画像から検出 → 照合 → 登録。検出器が必要。"""
        if self._detector is None:
            from app.face.detector import get_detector

            self._detector = get_detector()
        faces = self._detector.detect(image_bytes)
        return self.process_detections(photo, faces)

    def reprocess_photo(self, photo: Photo, image_bytes: bytes) -> list[PhotoPerson]:
        """既存の検出顔リンクを置き換えて、この写真を再度顔認識する。"""
        if self._detector is None:
            from app.face.detector import get_detector

            self._detector = get_detector()
        faces = self._detector.detect(image_bytes)

        old_person_ids = list(
            self.db.execute(
                select(PhotoPerson.person_id).where(
                    PhotoPerson.photo_id == photo.id,
                    PhotoPerson.person_id.isnot(None),
                )
            ).scalars()
        )
        CooccurrenceService(self.db).bump_pairs(old_person_ids, delta=-1)
        self.db.execute(delete(PhotoPerson).where(PhotoPerson.photo_id == photo.id))
        self.db.flush()
        return self.process_detections(photo, faces)
