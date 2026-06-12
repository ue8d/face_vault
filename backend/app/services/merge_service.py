"""人物統合。誤検出/重複（自動登録含む）を既存人物へ吸収し精度向上。

source の Embedding/写真リンク/ニック/タグ/イベント/共起を target へ移管後、source削除。
Embedding移管で target の参照ベクトルが増え照合精度が向上。
VectorIndex は match 時に embedding_id→person_id を DB参照で解決するため、
インデックス再構築は不要（person_id 付替で自動反映）。
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.api_query import ApiQuery
from app.models.cooccurrence import PersonCooccurrence
from app.models.face_import import FaceImport
from app.models.nickname import Nickname
from app.models.person import Person
from app.models.person_embedding import PersonEmbedding
from app.models.photo_person import PhotoPerson


class PersonMergeService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def merge(self, source_id: int, target_id: int) -> Person:
        if source_id == target_id:
            raise ValueError("source と target が同一")
        source = self.db.get(Person, source_id)
        target = self.db.get(Person, target_id)
        if source is None or target is None:
            raise ValueError("人物が存在しない")
        if source.environment_id != target.environment_id:
            raise ValueError("環境が異なる人物は統合できません")

        self._merge_photo_links(source_id, target_id)
        self._move_embeddings(source_id, target_id)
        self._merge_nicknames(source, target)
        self._merge_tags(source, target)
        self._merge_events(source, target)
        self._merge_cooccurrence(source_id, target_id)
        self._merge_external_ids(source, target)
        self._move_face_imports(source_id, target_id)
        self._move_learned_api_queries(source_id, target_id)

        self.db.delete(source)
        self.db.commit()
        self.db.refresh(target)
        return target

    def _merge_photo_links(self, source_id: int, target_id: int) -> None:
        # target が既に写る写真は重複(unique制約)になるため source側リンク削除
        target_photos = set(
            self.db.execute(
                select(PhotoPerson.photo_id).where(PhotoPerson.person_id == target_id)
            ).scalars()
        )
        links = self.db.execute(
            select(PhotoPerson).where(PhotoPerson.person_id == source_id)
        ).scalars().all()
        for link in links:
            if link.photo_id in target_photos:
                self.db.delete(link)
            else:
                link.person_id = target_id
                target_photos.add(link.photo_id)
        self.db.flush()

    def _move_embeddings(self, source_id: int, target_id: int) -> None:
        rows = self.db.execute(
            select(PersonEmbedding).where(PersonEmbedding.person_id == source_id)
        ).scalars().all()
        for r in rows:
            r.person_id = target_id
        self.db.flush()

    def _merge_nicknames(self, source: Person, target: Person) -> None:
        # delete-orphan 回避のためコレクション操作で再親付け
        existing = {n.name for n in target.nicknames}
        for n in list(source.nicknames):
            source.nicknames.remove(n)
            if n.name not in existing:
                target.nicknames.append(n)
                existing.add(n.name)
            # 重複は remove のみ → orphan として削除
        self.db.flush()

    def _merge_tags(self, source: Person, target: Person) -> None:
        have = {t.id for t in target.tags}
        for t in source.tags:
            if t.id not in have:
                target.tags.append(t)
                have.add(t.id)

    def _merge_events(self, source: Person, target: Person) -> None:
        have = {e.id for e in target.events}
        for e in source.events:
            if e.id not in have:
                target.events.append(e)
                have.add(e.id)

    def _merge_external_ids(self, source: Person, target: Person) -> None:
        # CSV再取込時に source の external_id で重複人物が復活しないよう target へ移管。
        # delete-orphan 回避のためコレクション操作で再親付け（ニックネームと同様）
        existing = {(e.source, e.external_id) for e in target.external_ids}
        for e in list(source.external_ids):
            source.external_ids.remove(e)
            if (e.source, e.external_id) not in existing:
                target.external_ids.append(e)
                existing.add((e.source, e.external_id))
            # 重複は remove のみ → orphan として削除
        self.db.flush()

    def _move_face_imports(self, source_id: int, target_id: int) -> None:
        rows = self.db.execute(
            select(FaceImport).where(FaceImport.person_id == source_id)
        ).scalars().all()
        for r in rows:
            r.person_id = target_id
        self.db.flush()

    def _move_learned_api_queries(self, source_id: int, target_id: int) -> None:
        rows = self.db.execute(
            select(ApiQuery).where(ApiQuery.learned_person_id == source_id)
        ).scalars().all()
        for r in rows:
            r.learned_person_id = target_id
        self.db.flush()

    def _merge_cooccurrence(self, source_id: int, target_id: int) -> None:
        rows = self.db.execute(
            select(PersonCooccurrence).where(
                (PersonCooccurrence.person_a_id == source_id)
                | (PersonCooccurrence.person_b_id == source_id)
            )
        ).scalars().all()
        for r in rows:
            other = r.person_b_id if r.person_a_id == source_id else r.person_a_id
            if other == target_id:
                self.db.delete(r)  # 自己ペア化 → 無意味
                continue
            a, b = sorted((target_id, other))
            existing = self.db.scalar(
                select(PersonCooccurrence).where(
                    PersonCooccurrence.person_a_id == a,
                    PersonCooccurrence.person_b_id == b,
                )
            )
            if existing is not None and existing.id != r.id:
                existing.count += r.count
                self.db.delete(r)
            else:
                r.person_a_id, r.person_b_id = a, b
        self.db.flush()
