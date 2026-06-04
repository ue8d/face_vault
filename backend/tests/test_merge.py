"""人物統合（誤検出/重複 → 既存人物へ吸収、精度向上）。"""
from __future__ import annotations

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.face.index import VectorIndex
from app.models.cooccurrence import PersonCooccurrence
from app.models.nickname import Nickname
from app.models.person import Person
from app.models.person_embedding import PersonEmbedding
from app.models.photo import Photo
from app.models.photo_person import PhotoPerson
from app.services.cooccurrence_service import CooccurrenceService
from app.services.face_service import FaceService
from app.services.merge_service import PersonMergeService

DIM = 512


def _unit(seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    v = rng.standard_normal(DIM).astype("float32")
    return v / np.linalg.norm(v)


def test_merge_moves_embeddings_and_resolves_to_target(db: Session) -> None:
    real = Person(name="本人")
    dup = Person(name="未確認人物", nicknames=[Nickname(name="重複ニック")])
    db.add_all([real, dup])
    db.flush()

    idx = VectorIndex(dim=DIM)
    svc = FaceService(db, idx, threshold=0.5)
    svc.register_embedding(real.id, _unit(1))
    dup_vec = _unit(2)
    svc.register_embedding(dup.id, dup_vec)
    db.commit()

    # 統合前: dup_vec は dup に解決
    assert svc.match(dup_vec, k=1)[0].person_id == dup.id

    target = PersonMergeService(db).merge(source_id=dup.id, target_id=real.id)

    assert db.get(Person, dup.id) is None  # source 削除
    # Embedding は target へ（2件）→ 参照増で精度向上
    n = db.scalar(select(func.count(PersonEmbedding.id)).where(PersonEmbedding.person_id == real.id))
    assert n == 2
    # 旧dupベクトルは target に解決（index再構築不要）
    assert svc.match(dup_vec, k=1)[0].person_id == real.id
    # ニックネーム移管
    assert "重複ニック" in [nk.name for nk in target.nicknames]


def test_merge_dedupes_photo_links_and_cooccurrence(db: Session) -> None:
    a = Person(name="A")
    b = Person(name="B")
    dup = Person(name="dup")
    db.add_all([a, b, dup])
    db.flush()

    p1 = Photo(path="1.jpg")
    p2 = Photo(path="2.jpg")
    db.add_all([p1, p2])
    db.flush()
    # p1: a, dup 両方 / p2: dup のみ
    db.add_all(
        [
            PhotoPerson(photo_id=p1.id, person_id=a.id),
            PhotoPerson(photo_id=p1.id, person_id=dup.id),
            PhotoPerson(photo_id=p2.id, person_id=dup.id),
        ]
    )
    db.flush()
    CooccurrenceService(db).bump_pairs([a.id, dup.id])  # a-dup 共起
    CooccurrenceService(db).bump_pairs([b.id, dup.id])  # b-dup 共起
    db.commit()

    PersonMergeService(db).merge(source_id=dup.id, target_id=a.id)

    # p1 は a に既存 → dup側リンク削除（重複回避）。p2 は a へ移管
    a_photos = set(
        db.execute(select(PhotoPerson.photo_id).where(PhotoPerson.person_id == a.id)).scalars()
    )
    assert a_photos == {p1.id, p2.id}
    assert db.get(Person, dup.id) is None
    # 共起: a-dup は自己ペア化で消滅、b-dup → b-a に付替
    pair = db.scalar(
        select(PersonCooccurrence).where(
            PersonCooccurrence.person_a_id == min(a.id, b.id),
            PersonCooccurrence.person_b_id == max(a.id, b.id),
        )
    )
    assert pair is not None and pair.count == 1
