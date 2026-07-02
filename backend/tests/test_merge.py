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


def test_merge_keeps_duplicate_photo_links_and_updates_cooccurrence(db: Session) -> None:
    """target が既に写る写真でも source側リンクは削除せず両方残す
    （1枚の写真に同一人物が複数回映るケースを許容するため）。"""
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

    # p1 は a のリンクが2件（元々のaリンク + dup→a付替）、p2 も a へ移管
    a_links = db.execute(
        select(PhotoPerson.photo_id).where(PhotoPerson.person_id == a.id)
    ).scalars().all()
    assert sorted(a_links) == sorted([p1.id, p1.id, p2.id])
    assert db.get(Person, dup.id) is None
    # 共起: a-dup は自己ペア化で消滅、b-dup → b-a に付替
    pair = db.scalar(
        select(PersonCooccurrence).where(
            PersonCooccurrence.person_a_id == min(a.id, b.id),
            PersonCooccurrence.person_b_id == max(a.id, b.id),
        )
    )
    assert pair is not None and pair.count == 1


def test_merge_moves_external_ids_and_face_imports(db: Session) -> None:
    """external_id/取込キューを target へ移管 → CSV再取込で重複人物が復活しない。"""
    from app.models.face_import import FaceImport
    from app.models.person_external_id import PersonExternalId

    real = Person(name="本人")
    dup = Person(name="重複")
    db.add_all([real, dup])
    db.flush()
    db.add(
        PersonExternalId(person_id=dup.id, source="friends_csv", external_id="ext-1")
    )
    db.add(FaceImport(person_id=dup.id, img_url="https://x/face.jpg", status="pending"))
    db.commit()

    PersonMergeService(db).merge(source_id=dup.id, target_id=real.id)

    ext = db.scalar(
        select(PersonExternalId).where(PersonExternalId.external_id == "ext-1")
    )
    assert ext is not None and ext.person_id == real.id
    imp = db.scalar(select(FaceImport).where(FaceImport.img_url == "https://x/face.jpg"))
    assert imp is not None and imp.person_id == real.id


def test_person_delete_cascades_cooccurrence(db: Session) -> None:
    """SQLiteでもFK有効 → 人物削除で共起行が孤児として残らない。"""
    a = Person(name="A")
    b = Person(name="B")
    db.add_all([a, b])
    db.flush()
    CooccurrenceService(db).bump_pairs([a.id, b.id])
    db.commit()

    from app.services.person_service import PersonService

    PersonService(db).delete(db.get(Person, b.id))

    assert db.scalar(select(func.count(PersonCooccurrence.id))) == 0
