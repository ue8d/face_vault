"""ルーター集約。API設計のエンドポイント群を束ねる。"""
from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import (
    api_external,
    environments,
    events,
    faces,
    identify,
    persons,
    photos,
    review,
    settings,
)

api_router = APIRouter()
api_router.include_router(photos.router, prefix="/photos", tags=["photos"])
api_router.include_router(persons.router, prefix="/persons", tags=["persons"])
api_router.include_router(events.router, prefix="/events", tags=["events"])
api_router.include_router(faces.router, tags=["faces"])
api_router.include_router(review.router, tags=["review"])
api_router.include_router(settings.router, tags=["settings"])
api_router.include_router(environments.router, tags=["environments"])
api_router.include_router(identify.router, tags=["identify"])
api_router.include_router(api_external.router)
