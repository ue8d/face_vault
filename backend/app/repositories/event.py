"""イベント リポジトリ。"""
from __future__ import annotations

from sqlalchemy import select

from app.models.event import Event
from app.repositories.base import BaseRepository


class EventRepository(BaseRepository[Event]):
    model = Event

    def search_by_name(self, q: str, *, limit: int = 100, offset: int = 0) -> list[Event]:
        stmt = (
            self._scoped(select(Event).where(Event.name.ilike(f"%{q}%")))
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.scalars(stmt).all())
