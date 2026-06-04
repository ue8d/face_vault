"""人物 リポジトリ。"""
from __future__ import annotations

from sqlalchemy import func, or_, select

from app.models.nickname import Nickname
from app.models.person import Person
from app.repositories.base import BaseRepository


class PersonRepository(BaseRepository[Person]):
    model = Person

    def count(self, q: str | None = None) -> int:
        if q:
            stmt = (
                select(func.count(func.distinct(Person.id)))
                .outerjoin(Nickname)
                .where(or_(Person.name.ilike(f"%{q}%"), Nickname.name.ilike(f"%{q}%")))
            )
        else:
            stmt = select(func.count(Person.id))
        return int(self.db.scalar(stmt) or 0)

    def list(self, *, limit: int = 100, offset: int = 0) -> list[Person]:
        stmt = select(Person).order_by(Person.id).limit(limit).offset(offset)
        return list(self.db.scalars(stmt).all())

    def search_by_name(self, q: str, *, limit: int = 100, offset: int = 0) -> list[Person]:
        stmt = (
            select(Person)
            .outerjoin(Nickname)
            .where(or_(Person.name.ilike(f"%{q}%"), Nickname.name.ilike(f"%{q}%")))
            .distinct()
            .order_by(Person.id)
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.scalars(stmt).all())
