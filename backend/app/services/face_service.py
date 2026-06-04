"""顔処理サービス。検出顔の照合・人物Embedding登録・写真処理。

マルチモデル対応: insightface / face01 等を並行運用。モデル間の埋め込みは別空間
のため、生コサイン類似を直接比較せず、モデル別閾値からの「マージン(score-threshold)」
で正規化して統合（person単位で max margin のモデルを採用）。

VectorIndex はモデル別（registry.get_index(model_key)）。index id 空間 =
person_embeddings.id。検出顔の埋め込みは face_embeddings(model_key) に保持。
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.face import embedding as emb
from app.face.detector import DetectedFace, FaceDetector
from app.face.embedder import INSIGHTFACE, configure_runtime_embedders
from app.face.index import VectorIndex
from app.models.face_embedding import FaceEmbedding
from app.models.person_embedding import PersonEmbedding
from app.models.photo import Photo
from app.models.photo_person import PhotoPerson
from app.services.cooccurrence_service import CooccurrenceService

settings = get_settings()


@dataclass
class Candidate:
    person_id: int
    score: float  # 採用モデルの生コサイン類似（UI表示用。モデル間で直接比較不可）
    margin: float = 0.0  # score - そのモデルの閾値（統合・採否判定の基準）
    model_key: str = INSIGHTFACE


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
        self.index = index  # insightface 用（後方互換: 既存呼び出しが渡す index）
        self._indexes: dict[str, VectorIndex] = {INSIGHTFACE: index}
        self._detector = detector
        from app.services.settings_service import SettingsService

        cfg = SettingsService(db)
        def cfg_float(key: str, default: float) -> float:
            value = cfg.value(key)
            return default if value is None else float(value)

        def cfg_int(key: str, default: int) -> int:
            value = cfg.value(key)
            return default if value is None else int(value)

        if threshold is not None:
            self.threshold = threshold
        else:
            self.threshold = float(cfg.value("match_threshold") or 0.35)
        self.min_det_score = cfg_float("face_min_det_score", 0.0)
        self.min_px = cfg_int("face_min_px", 0)
        self._face01_threshold = cfg_float("face01_threshold", 0.4)
        self.online_learning_enabled = bool(cfg.value("online_learning_enabled"))
        self.online_learning_min_margin = cfg_float("online_learning_min_margin", 0.2)
        self.online_learning_min_separation = cfg_float(
            "online_learning_min_separation", 0.05
        )
        self.online_learning_min_centroid_similarity = cfg_float(
            "online_learning_min_centroid_similarity", 0.45
        )
        self.online_learning_duplicate_similarity = cfg_float(
            "online_learning_duplicate_similarity", 0.995
        )
        self.online_learning_max_embeddings = cfg_int(
            "online_learning_max_embeddings_per_person_model", 50
        )
        configure_runtime_embedders(
            face01_enabled=bool(cfg.value("face01_enabled")),
            face01_model_path=str(cfg.value("face01_model_path") or ""),
        )

    # --- モデル別 index / 閾値 ---
    def _index_for(self, model_key: str) -> VectorIndex:
        idx = self._indexes.get(model_key)
        if idx is None:
            from app.face.registry import get_index

            idx = get_index(model_key)
            self._indexes[model_key] = idx
        return idx

    def _threshold_for(self, model_key: str) -> float:
        if model_key == INSIGHTFACE:
            return self.threshold
        return self._face01_threshold

    def quality_ok(self, f: DetectedFace) -> bool:
        """参照ベクトル登録に足る品質か（検出信頼度・顔サイズ）。"""
        _, _, w, h = f.bbox
        return f.det_score >= self.min_det_score and max(w, h) >= self.min_px

    # --- インデックス構築 ---
    def rebuild_index(self) -> int:
        """全モデルの index を person_embeddings から再構築。登録総数を返す。"""
        rows = self.db.execute(
            select(
                PersonEmbedding.id, PersonEmbedding.model_key, PersonEmbedding.embedding
            )
        ).all()
        by_model: dict[str, list[tuple[int, np.ndarray]]] = {}
        for rid, model_key, buf in rows:
            by_model.setdefault(model_key, []).append((rid, emb.from_bytes(buf)))
        # insightface は渡された index を必ず再構築（空でもリセット）
        for model_key in {INSIGHTFACE, *by_model.keys()}:
            self._index_for(model_key).build(by_model.get(model_key, []))
        return sum(len(v) for v in by_model.values())

    # --- 人物Embedding登録 ---
    def register_embedding(
        self,
        person_id: int,
        vec: np.ndarray,
        *,
        model_key: str = INSIGHTFACE,
        source_photo_id: int | None = None,
    ) -> PersonEmbedding:
        row = PersonEmbedding(
            person_id=person_id,
            embedding=emb.to_bytes(emb.l2_normalize(vec)),
            dim=int(vec.shape[0]),
            model_key=model_key,
            source_photo_id=source_photo_id,
        )
        self.db.add(row)
        self.db.flush()
        self._index_for(model_key).add(row.id, vec)
        return row

    # --- 照合 ---
    def match(
        self, query: dict[str, np.ndarray] | np.ndarray, *, k: int = 5
    ) -> list[Candidate]:
        """検出顔ベクトルに近い人物候補を返す。

        各モデルで近傍検索 → margin(=score-閾値) に正規化 → person単位で
        max margin のモデルを採用。margin 降順に並べる。
        query は {model_key: vec}（マルチ）または単一 ndarray（=insightface・後方互換）。
        """
        if isinstance(query, np.ndarray):
            query = {INSIGHTFACE: query}

        # person_id -> (margin, raw_score, model_key)
        best: dict[int, tuple[float, float, str]] = {}
        for model_key, vec in query.items():
            hits = self._index_for(model_key).search(vec, k=k)
            if not hits:
                continue
            ids = [eid for eid, _ in hits]
            emb_to_person = dict(
                self.db.execute(
                    select(PersonEmbedding.id, PersonEmbedding.person_id).where(
                        PersonEmbedding.id.in_(ids)
                    )
                ).all()
            )
            thr = self._threshold_for(model_key)
            for eid, score in hits:
                pid = emb_to_person.get(eid)
                if pid is None:
                    continue
                margin = score - thr
                cur = best.get(pid)
                if cur is None or margin > cur[0]:
                    best[pid] = (margin, score, model_key)

        cands = [
            Candidate(person_id=p, score=s, margin=m, model_key=mk)
            for p, (m, s, mk) in best.items()
        ]
        cands.sort(key=lambda c: c.margin, reverse=True)
        return cands

    # --- 検出顔の埋め込み保存（face_embeddings 子テーブル） ---
    def _attach_embeddings(self, link: PhotoPerson, embeddings: dict[str, np.ndarray]) -> None:
        for model_key, vec in embeddings.items():
            link.embeddings.append(
                FaceEmbedding(
                    model_key=model_key,
                    embedding=emb.to_bytes(emb.l2_normalize(vec)),
                    dim=int(vec.shape[0]),
                )
            )

    def _existing_person_vectors(self, person_id: int, model_key: str) -> list[np.ndarray]:
        rows = self.db.execute(
            select(PersonEmbedding.embedding).where(
                PersonEmbedding.person_id == person_id,
                PersonEmbedding.model_key == model_key,
            )
        ).scalars()
        return [emb.from_bytes(buf) for buf in rows]

    def _has_embedding_from_photo(
        self, person_id: int, model_key: str, source_photo_id: int
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

    def _centroid_similarity(self, vec: np.ndarray, existing: list[np.ndarray]) -> float:
        if not existing:
            return 1.0
        centroid = emb.l2_normalize(np.mean(np.vstack(existing), axis=0))
        if np.linalg.norm(centroid) == 0:
            return 0.0
        return emb.cosine_similarity(vec, centroid)

    def _maybe_online_learn(
        self,
        person_id: int,
        face: DetectedFace,
        top: Candidate,
        candidates: list[Candidate],
        *,
        source_photo_id: int,
    ) -> None:
        """高信頼な既存人物マッチだけを代表ベクトルへ追加する。"""
        if not self.online_learning_enabled:
            return
        if top.margin < self.online_learning_min_margin:
            return
        if not self.quality_ok(face):
            return
        if len(candidates) > 1:
            separation = top.margin - candidates[1].margin
            if separation < self.online_learning_min_separation:
                return

        vec = face.embeddings.get(top.model_key)
        if vec is None:
            return
        if self._has_embedding_from_photo(person_id, top.model_key, source_photo_id):
            return

        existing = self._existing_person_vectors(person_id, top.model_key)
        if len(existing) >= self.online_learning_max_embeddings:
            return

        normalized = emb.l2_normalize(vec)
        if existing:
            nearest = max(emb.cosine_similarity(normalized, current) for current in existing)
            if nearest >= self.online_learning_duplicate_similarity:
                return
            if (
                self._centroid_similarity(normalized, existing)
                < self.online_learning_min_centroid_similarity
            ):
                return

        self.register_embedding(
            person_id,
            normalized,
            model_key=top.model_key,
            source_photo_id=source_photo_id,
        )

    # --- 写真処理（検出済みfacesから） ---
    def process_detections(
        self, photo: Photo, faces: list[DetectedFace], *, auto_enroll: bool | None = None
    ) -> list[PhotoPerson]:
        """検出顔を照合 → photo_persons + face_embeddings 登録。

        - 統合margin>=0: 既存人物に紐付け
        - 未一致 & auto_enroll: 新規人物を自動作成し全モデルEmbedding登録
        - 未一致 & not auto_enroll: person_id=None（未照合のまま手動確定待ち）
        """
        if auto_enroll is None:
            from app.services.settings_service import SettingsService

            auto_enroll = bool(SettingsService(self.db).value("auto_enroll_faces"))

        links: list[PhotoPerson] = []
        used: set[int] = set()  # 同一写真内で同一人物への重複リンク防止（uq_photo_person）
        # 各顔の最良候補を先に算出し、margin の高い順に確定（重複時は高margin側を残す）
        scored = [(f, self.match(f.embeddings, k=3)) for f in faces]
        scored.sort(key=lambda t: t[1][0].margin if t[1] else -1.0, reverse=True)
        for f, candidates in scored:
            top = candidates[0] if candidates else None
            matched = top.person_id if top and top.margin >= 0 else None

            if matched is not None and matched in used:
                matched = None  # 既に同写真で使用済み → 未照合化（自動登録もしない）
            elif matched is None and auto_enroll and self.quality_ok(f):
                # 品質ゲート通過時のみ自動登録（低品質は未照合のまま確認キューへ）
                matched = self._auto_create_person(f, source_photo_id=photo.id)

            if matched is not None:
                used.add(matched)
                if top is not None:
                    self._maybe_online_learn(
                        matched,
                        f,
                        top,
                        candidates,
                        source_photo_id=photo.id,
                    )

            x, y, w, h = f.bbox
            link = PhotoPerson(
                photo_id=photo.id,
                person_id=matched,
                confidence=top.score if top else None,
                bbox=f"{x},{y},{w},{h}",
            )
            self._attach_embeddings(link, f.embeddings)
            self.db.add(link)
            links.append(link)
        self.db.flush()

        person_ids = [link.person_id for link in links if link.person_id is not None]
        CooccurrenceService(self.db).bump_pairs(person_ids)
        return links

    def _auto_create_person(self, f: DetectedFace, *, source_photo_id: int) -> int:
        """未一致顔から新規人物を自動作成し、全モデルのEmbeddingを登録。person_id を返す。"""
        from app.models.person import Person

        person = Person(name="（自動登録）", memo="顔認識による自動登録。確認/改名/統合してください。")
        self.db.add(person)
        self.db.flush()
        person.name = f"未確認人物 #{person.id}"
        for model_key, vec in f.embeddings.items():
            self.register_embedding(
                person.id, vec, model_key=model_key, source_photo_id=source_photo_id
            )
        return person.id

    # --- 参照顔登録（保存済み写真の顔を人物代表として登録） ---
    def register_reference(
        self, person_id: int, face: DetectedFace, photo_id: int
    ) -> PersonEmbedding | None:
        """検出顔を人物の代表Embeddingとして全モデル登録し、写真リンクも作成。

        元画像(photo_id)に紐付くため、参照写真が本人の写真一覧に確定状態で出る。
        戻り値は insightface の PersonEmbedding（無ければ None）。
        """
        primary: PersonEmbedding | None = None
        for model_key, vec in face.embeddings.items():
            row = self.register_embedding(
                person_id, vec, model_key=model_key, source_photo_id=photo_id
            )
            if model_key == INSIGHTFACE:
                primary = row
        x, y, w, h = face.bbox
        link = PhotoPerson(
            photo_id=photo_id,
            person_id=person_id,
            confidence=1.0,
            bbox=f"{x},{y},{w},{h}",
        )
        self._attach_embeddings(link, face.embeddings)
        self.db.add(link)
        self.db.flush()
        return primary

    # --- 手動確定（候補→人物紐付け） ---
    def confirm_face(self, link: PhotoPerson, person_id: int) -> PhotoPerson:
        """検出顔を人物に確定。その顔の全モデルEmbeddingを人物代表として登録 + 共起更新。"""
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
        for fe in link.embeddings:
            self.register_embedding(
                person_id,
                emb.from_bytes(fe.embedding),
                model_key=fe.model_key,
                source_photo_id=link.photo_id,
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
        old_link_ids = select(PhotoPerson.id).where(PhotoPerson.photo_id == photo.id)
        self.db.execute(
            delete(FaceEmbedding).where(FaceEmbedding.photo_person_id.in_(old_link_ids))
        )
        self.db.execute(delete(PhotoPerson).where(PhotoPerson.photo_id == photo.id))
        self.db.flush()
        return self.process_detections(photo, faces)
