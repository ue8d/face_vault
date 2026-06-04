"""イベント サービス。"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.event import Event
from app.models.person import Person
from app.repositories.event import EventRepository
from app.schemas.event import EventCreate, EventUpdate


class EventService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.events = EventRepository(db)

    def list(self, *, q: str | None = None, limit: int = 100, offset: int = 0) -> list[Event]:
        if q:
            return self.events.search_by_name(q, limit=limit, offset=offset)
        return self.events.list(limit=limit, offset=offset)

    def get(self, event_id: int) -> Event | None:
        return self.events.get(event_id)

    def count(self) -> int:
        return self.events.count()

    def get_person(self, person_id: int) -> Person | None:
        return self.db.get(Person, person_id)

    def create(self, data: EventCreate) -> Event:
        event = Event(name=data.name, memo=data.memo)
        self.events.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event

    def update(self, event: Event, data: EventUpdate) -> Event:
        if data.name is not None:
            event.name = data.name
        if data.memo is not None:
            event.memo = data.memo
        self.db.commit()
        self.db.refresh(event)
        return event

    def add_person(self, event: Event, person: Person) -> Person:
        if all(existing.id != person.id for existing in event.persons):
            event.persons.append(person)
            self.db.commit()
        self.db.refresh(person)
        return person

    def remove_person(self, event: Event, person: Person) -> None:
        event.persons = [existing for existing in event.persons if existing.id != person.id]
        self.db.commit()

    def delete(self, event: Event) -> None:
        self.events.delete(event)
        self.db.commit()
