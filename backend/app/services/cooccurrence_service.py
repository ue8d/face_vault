"""共起人物 集計更新。person_a_id < person_b_id で正規化。"""
from __future__ import annotations

from itertools import combinations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.cooccurrence import PersonCooccurrence


class CooccurrenceService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def bump_pairs(self, person_ids: list[int], *, delta: int = 1) -> None:
        """同一写真内 人物群の全ペア共起カウントを増分。"""
        uniq = sorted(set(person_ids))
        for a, b in combinations(uniq, 2):
            row = self.db.scalar(
                select(PersonCooccurrence).where(
                    PersonCooccurrence.person_a_id == a,
                    PersonCooccurrence.person_b_id == b,
                )
            )
            if row is None:
                if delta <= 0:
                    continue
                row = PersonCooccurrence(person_a_id=a, person_b_id=b, count=delta)
                self.db.add(row)
            else:
                row.count += delta
                if row.count <= 0:
                    self.db.delete(row)
        self.db.flush()

    def top_companions(self, person_id: int, *, limit: int = 5) -> list[tuple[int, int]]:
        """(相手person_id, 共起回数) を回数降順。"""
        rows = self.db.execute(
            select(PersonCooccurrence).where(
                (PersonCooccurrence.person_a_id == person_id)
                | (PersonCooccurrence.person_b_id == person_id)
            )
        ).scalars().all()
        pairs = [
            (r.person_b_id if r.person_a_id == person_id else r.person_a_id, r.count)
            for r in rows
        ]
        pairs.sort(key=lambda x: x[1], reverse=True)
        return pairs[:limit]
