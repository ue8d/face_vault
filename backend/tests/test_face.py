"""顔照合パイプライン（検出器を注入してinsightface無しで検証）。"""
from __future__ import annotations

import numpy as np
from sqlalchemy.orm import Session

from app.face.detector import DetectedFace
from app.face.index import VectorIndex
from app.models.event import Event
from app.models.person import Person
from app.models.photo import Photo
from app.models.photo_person import PhotoPerson
from app.services.cooccurrence_service import CooccurrenceService
from app.services.face_service import FaceService

DIM = 512


def _unit(seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    v = rng.standard_normal(DIM).astype("float32")
    return v / np.linalg.norm(v)


class FakeDetector:
    """与えた埋め込み列をそのまま検出顔として返す。"""

    def __init__(self, embeddings: list[np.ndarray]) -> None:
        self._e = embeddings

    def detect(self, image_bytes: bytes) -> list[DetectedFace]:
        return [DetectedFace(bbox=(0, 0, 10, 10), embedding=e) for e in self._e]


def _mk_person(db: Session, name: str) -> Person:
    p = Person(name=name)
    db.add(p)
    db.flush()
    return p


def test_index_backend_and_search(db: Session) -> None:
    idx = VectorIndex(dim=DIM)
    assert idx.backend in {"faiss", "numpy"}
    idx.build([(1, _unit(1)), (2, _unit(2))])
    hits = idx.search(_unit(1), k=2)
    assert hits[0][0] == 1 and hits[0][1] > 0.99


def test_register_and_match(db: Session) -> None:
    alice = _mk_person(db, "Alice")
    bob = _mk_person(db, "Bob")
    svc = FaceService(db, VectorIndex(dim=DIM), threshold=0.5)
    va, vb = _unit(10), _unit(20)
    svc.register_embedding(alice.id, va)
    svc.register_embedding(bob.id, vb)

    cands = svc.match(va + 0.01 * _unit(99), k=2)
    assert cands and cands[0].person_id == alice.id
    assert cands[0].score >= 0.5


def test_rebuild_index_from_db(db: Session) -> None:
    """再起動相当: person_embeddings からインデックス再構築 → 照合可。"""
    alice = _mk_person(db, "Alice")
    bob = _mk_person(db, "Bob")
    va, vb = _unit(10), _unit(20)
    FaceService(db, VectorIndex(dim=DIM)).register_embedding(alice.id, va)
    FaceService(db, VectorIndex(dim=DIM)).register_embedding(bob.id, vb)
    db.commit()

    # 空の新インデックスで再構築（DBが正本）
    fresh = VectorIndex(dim=DIM)
    svc = FaceService(db, fresh, threshold=0.5)
    assert svc.rebuild_index() == 2
    cands = svc.match(va, k=1)
    assert cands and cands[0].person_id == alice.id


def test_process_detections_assigns_and_cooccurs(db: Session) -> None:
    alice = _mk_person(db, "Alice")
    bob = _mk_person(db, "Bob")
    va, vb = _unit(10), _unit(20)
    svc = FaceService(db, VectorIndex(dim=DIM), threshold=0.5)
    svc.register_embedding(alice.id, va)
    svc.register_embedding(bob.id, vb)

    photo = Photo(path="p.jpg")
    db.add(photo)
    db.flush()
    svc._detector = FakeDetector([va, vb])
    links = svc.process_photo(photo, b"img")

    assigned = sorted(link.person_id for link in links)
    assert assigned == sorted([alice.id, bob.id])
    # 共起: Alice-Bob ペア +1
    comp = CooccurrenceService(db).top_companions(alice.id)
    assert comp and comp[0] == (bob.id, 1)


def test_unmatched_face_stays_null_without_autoenroll(db: Session) -> None:
    svc = FaceService(db, VectorIndex(dim=DIM), threshold=0.9)
    photo = Photo(path="p.jpg")
    db.add(photo)
    db.flush()
    svc._detector = FakeDetector([_unit(123)])  # 空インデックス → 候補なし
    links = svc.process_detections(photo, svc._detector.detect(b""), auto_enroll=False)
    assert links[0].person_id is None


def test_autoenroll_creates_new_person(db: Session) -> None:
    from sqlalchemy import func, select

    from app.models.person_embedding import PersonEmbedding

    svc = FaceService(db, VectorIndex(dim=DIM), threshold=0.5)
    photo = Photo(path="p.jpg")
    db.add(photo)
    db.flush()
    faces = [DetectedFace(bbox=(0, 0, 120, 120), embedding=_unit(7), det_score=0.9)]
    links = svc.process_detections(photo, faces, auto_enroll=True)
    pid = links[0].person_id
    assert pid is not None
    person = db.get(Person, pid)
    assert person.name == f"未確認人物 #{pid}"
    # Embedding が登録され、次回照合で命中
    n = db.scalar(select(func.count(PersonEmbedding.id)).where(PersonEmbedding.person_id == pid))
    assert n == 1
    assert svc.match(_unit(7), k=1)[0].person_id == pid


def test_confirm_face(db: Session) -> None:
    alice = _mk_person(db, "Alice")
    svc = FaceService(db, VectorIndex(dim=DIM), threshold=0.99)
    photo = Photo(path="p.jpg")
    db.add(photo)
    db.flush()
    link = PhotoPerson(
        photo_id=photo.id, person_id=None, embedding=_unit(5).astype("<f4").tobytes()
    )
    db.add(link)
    db.flush()

    svc.confirm_face(link, alice.id)
    assert link.person_id == alice.id
    # 確定で人物Embedding登録 → 再照合で命中
    svc.rebuild_index()
    import numpy as np

    from app.face.embedding import from_bytes

    cands = svc.match(from_bytes(link.embedding), k=1)
    assert cands and cands[0].person_id == alice.id
