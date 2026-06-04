"""確認キュー。割当が必要 or 低信頼の検出顔を、候補付きで提示。

半自動運用での精度向上の主経路: ここで素早く確定すると本人ベクトルが増える。
対象: 未照合(person_id NULL) の顔 / 信頼度が review_confidence 未満の顔。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.face import embedding as emb
from app.face.index import VectorIndex
from app.models.person import Person
from app.models.photo_person import PhotoPerson
from app.services.face_service import FaceService
from app.services.settings_service import SettingsService


@dataclass
class Candidate:
    person_id: int
    name: str
    score: float


@dataclass
class ReviewItem:
    link_id: int
    photo_id: int
    bbox: str | None
    confidence: float | None
    person_id: int | None
    person_name: str | None
    candidates: list[Candidate] = field(default_factory=list)


class ReviewService:
    def __init__(self, db: Session, index: VectorIndex) -> None:
        self.db = db
        self.index = index

    def _criteria(self):
        rc = float(SettingsService(self.db).value("review_confidence") or 0.45)
        return or_(
            and_(PhotoPerson.person_id.is_(None), PhotoPerson.embeddings.any()),
            and_(PhotoPerson.confidence.is_not(None), PhotoPerson.confidence < rc),
        )

    def count(self) -> int:
        from sqlalchemy import func

        return int(
            self.db.scalar(
                select(func.count(PhotoPerson.id)).where(self._criteria())
            )
            or 0
        )

    def faces(self, *, limit: int = 30, offset: int = 0) -> list[ReviewItem]:
        links = self.db.execute(
            select(PhotoPerson)
            .where(self._criteria())
            .order_by(PhotoPerson.id)
            .limit(limit)
            .offset(offset)
        ).scalars().all()

        face = FaceService(self.db, self.index)
        items: list[ReviewItem] = []
        need_ids: set[int] = set()
        raw: list[tuple[PhotoPerson, list]] = []
        for link in links:
            cands = []
            embs = {fe.model_key: emb.from_bytes(fe.embedding) for fe in link.embeddings}
            if embs:
                cands = face.match(embs, k=3)
            raw.append((link, cands))
            for c in cands:
                need_ids.add(c.person_id)
            if link.person_id:
                need_ids.add(link.person_id)

        names = dict(
            self.db.execute(select(Person.id, Person.name).where(Person.id.in_(need_ids))).all()
        )
        for link, cands in raw:
            items.append(
                ReviewItem(
                    link_id=link.id,
                    photo_id=link.photo_id,
                    bbox=link.bbox,
                    confidence=link.confidence,
                    person_id=link.person_id,
                    person_name=names.get(link.person_id) if link.person_id else None,
                    candidates=[
                        Candidate(c.person_id, names.get(c.person_id, f"#{c.person_id}"), round(c.score, 4))
                        for c in cands
                    ],
                )
            )
        return items
