"""統合候補サジェスト。別人物のベクトルが近接するペアを検出して提案。

auto-enroll で量産される重複人物（同一人物が複数の未確認人物に分かれる等）を
掃除するための提案。却下したペアは merge_dismissals に記録し再提案しない。
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.face import embedding as emb
from app.face.index import VectorIndex
from app.models.merge_dismissal import MergeDismissal
from app.models.person import Person
from app.models.person_embedding import PersonEmbedding
from app.services.settings_service import SettingsService


@dataclass
class Suggestion:
    person_a_id: int
    person_a_name: str
    person_b_id: int
    person_b_name: str
    score: float


class MergeSuggestService:
    def __init__(self, db: Session, index: VectorIndex) -> None:
        self.db = db
        self.index = index

    def suggestions(self, *, limit: int = 20, threshold: float | None = None) -> list[Suggestion]:
        if threshold is None:
            threshold = float(SettingsService(self.db).value("merge_suggest_threshold") or 0.5)

        rows = self.db.execute(
            select(PersonEmbedding.id, PersonEmbedding.person_id, PersonEmbedding.embedding)
        ).all()
        emb_person = {eid: pid for eid, pid, _ in rows}

        best: dict[tuple[int, int], float] = {}
        for eid, pid, buf in rows:
            for hid, score in self.index.search(emb.from_bytes(buf), k=5):
                if hid == eid or score < threshold:
                    continue
                other = emb_person.get(hid)
                if other is None or other == pid:
                    continue
                key = (min(pid, other), max(pid, other))
                if key not in best or score > best[key]:
                    best[key] = score

        if not best:
            return []

        dismissed = {
            (a, b)
            for a, b in self.db.execute(
                select(MergeDismissal.person_a_id, MergeDismissal.person_b_id)
            ).all()
        }
        pairs = [(k, s) for k, s in best.items() if k not in dismissed]
        pairs.sort(key=lambda t: t[1], reverse=True)
        pairs = pairs[:limit]

        ids = {i for (a, b), _ in pairs for i in (a, b)}
        names = dict(
            self.db.execute(select(Person.id, Person.name).where(Person.id.in_(ids))).all()
        )
        return [
            Suggestion(
                person_a_id=a,
                person_a_name=names.get(a, f"#{a}"),
                person_b_id=b,
                person_b_name=names.get(b, f"#{b}"),
                score=round(s, 4),
            )
            for (a, b), s in pairs
        ]

    def dismiss(self, person_id_1: int, person_id_2: int) -> None:
        a, b = sorted((person_id_1, person_id_2))
        if self.db.get(MergeDismissal, (a, b)) is None:
            self.db.add(MergeDismissal(person_a_id=a, person_b_id=b))
            self.db.commit()
