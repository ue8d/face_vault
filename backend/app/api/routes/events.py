"""イベントエンドポイント。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.schemas.event import EventCreate, EventOut, EventUpdate
from app.schemas.person import PersonOut
from app.services.event_service import EventService

router = APIRouter()


def _service(db: Session = Depends(get_db)) -> EventService:
    return EventService(db)


@router.get("", response_model=list[EventOut])
def list_events(
    q: str | None = None,
    limit: int = 100,
    offset: int = 0,
    svc: EventService = Depends(_service),
) -> list:
    return svc.list(q=q, limit=limit, offset=offset)


@router.post("", response_model=EventOut, status_code=status.HTTP_201_CREATED)
def create_event(data: EventCreate, svc: EventService = Depends(_service)):
    return svc.create(data)


@router.get("/count")
def count_events(svc: EventService = Depends(_service)) -> dict:
    return {"count": svc.count()}


@router.get("/{event_id}", response_model=EventOut)
def get_event(event_id: int, svc: EventService = Depends(_service)):
    event = svc.get(event_id)
    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "event not found")
    return event


@router.get("/{event_id}/persons", response_model=list[PersonOut])
def list_event_persons(event_id: int, svc: EventService = Depends(_service)):
    event = svc.get(event_id)
    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "event not found")
    return event.persons


@router.post("/{event_id}/persons/{person_id}", response_model=PersonOut)
def add_event_person(
    event_id: int,
    person_id: int,
    svc: EventService = Depends(_service),
):
    event = svc.get(event_id)
    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "event not found")
    person = svc.get_person(person_id)
    if person is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "person not found")
    return svc.add_person(event, person)


@router.delete("/{event_id}/persons/{person_id}")
def remove_event_person(
    event_id: int,
    person_id: int,
    svc: EventService = Depends(_service),
) -> Response:
    event = svc.get(event_id)
    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "event not found")
    person = svc.get_person(person_id)
    if person is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "person not found")
    svc.remove_person(event, person)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/{event_id}", response_model=EventOut)
def update_event(event_id: int, data: EventUpdate, svc: EventService = Depends(_service)):
    event = svc.get(event_id)
    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "event not found")
    return svc.update(event, data)


@router.delete("/{event_id}")
def delete_event(event_id: int, svc: EventService = Depends(_service)) -> Response:
    event = svc.get(event_id)
    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "event not found")
    svc.delete(event)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
