"""品質ゲート / 確認キュー / 統合候補。"""
from __future__ import annotations

import numpy as np
from sqlalchemy.orm import Session

from app.face import embedding as emb
from app.face.detector import DetectedFace
from app.face.index import VectorIndex
from app.models.person import Person
from app.models.photo import Photo
from app.models.photo_person import PhotoPerson
from app.services.face_service import FaceService
from app.services.merge_suggest_service import MergeSuggestService
from app.services.review_service import ReviewService

DIM = 512


def _unit(seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    v = rng.standard_normal(DIM).astype("float32")
    return v / np.linalg.norm(v)


def _person(db: Session, name: str) -> Person:
    p = Person(name=name)
    db.add(p)
    db.flush()
    return p


def test_quality_gate_blocks_small_face(db: Session) -> None:
    svc = FaceService(db, VectorIndex(dim=DIM), threshold=0.5)
    photo = Photo(path="p.jpg")
    db.add(photo)
    db.flush()
    # 小さすぎる顔(10px) → 自動登録されず未照合のまま
    small = [DetectedFace(bbox=(0, 0, 10, 10), embedding=_unit(1), det_score=0.9)]
    links = svc.process_detections(photo, small, auto_enroll=True)
    assert links[0].person_id is None


def test_review_queue_lists_unmatched_with_candidates(db: Session) -> None:
    idx = VectorIndex(dim=DIM)
    svc = FaceService(db, idx, threshold=0.5)
    alice = _person(db, "Alice")
    svc.register_embedding(alice.id, _unit(10))
    photo = Photo(path="p.jpg")
    db.add(photo)
    db.flush()
    # 未照合の顔（aliceに近い）
    link = PhotoPerson(
        photo_id=photo.id, person_id=None, embedding=emb.to_bytes(_unit(10)), bbox="0,0,100,100"
    )
    db.add(link)
    db.flush()

    review = ReviewService(db, idx)
    assert review.count() >= 1
    items = review.faces(limit=10)
    target = next(i for i in items if i.link_id == link.id)
    assert target.person_id is None
    assert target.candidates and target.candidates[0].person_id == alice.id


def test_confirm_removes_from_review(db: Session) -> None:
    idx = VectorIndex(dim=DIM)
    svc = FaceService(db, idx, threshold=0.5)
    alice = _person(db, "Alice")
    svc.register_embedding(alice.id, _unit(10))
    photo = Photo(path="p.jpg")
    db.add(photo)
    db.flush()
    # 低信頼マッチ（confidence < review_confidence 0.45）
    link = PhotoPerson(
        photo_id=photo.id,
        person_id=alice.id,
        confidence=0.3,
        embedding=emb.to_bytes(_unit(10)),
        bbox="0,0,100,100",
    )
    db.add(link)
    db.flush()
    review = ReviewService(db, idx)
    assert any(i.link_id == link.id for i in review.faces(limit=50))

    svc.confirm_face(link, alice.id)  # 確定 → confidence=1.0
    assert not any(i.link_id == link.id for i in review.faces(limit=50))


def test_merge_suggestion_and_dismiss(db: Session) -> None:
    idx = VectorIndex(dim=DIM)
    svc = FaceService(db, idx, threshold=0.5)
    a = _person(db, "未確認A")
    b = _person(db, "未確認B")
    base = _unit(20)
    svc.register_embedding(a.id, base)
    svc.register_embedding(b.id, base + 0.02 * _unit(99))  # ほぼ同一 → 統合候補
    db.commit()

    ms = MergeSuggestService(db, idx)
    sugg = ms.suggestions(threshold=0.5)
    assert any({s.person_a_id, s.person_b_id} == {a.id, b.id} for s in sugg)

    ms.dismiss(a.id, b.id)
    sugg2 = ms.suggestions(threshold=0.5)
    assert not any({s.person_a_id, s.person_b_id} == {a.id, b.id} for s in sugg2)
