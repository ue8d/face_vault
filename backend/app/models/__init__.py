"""モデル集約。Alembic autogenerate / メタデータ解決のため全モデルを import。"""
from __future__ import annotations

from app.db.base import Base
from app.models.app_setting import AppSetting
from app.models.associations import event_persons, person_tags
from app.models.cooccurrence import PersonCooccurrence
from app.models.event import Event
from app.models.face_embedding import FaceEmbedding
from app.models.face_import import FaceImport
from app.models.merge_dismissal import MergeDismissal
from app.models.nickname import Nickname
from app.models.person import Person
from app.models.person_external_id import PersonExternalId
from app.models.person_embedding import PersonEmbedding
from app.models.photo import Photo
from app.models.photo_person import PhotoPerson
from app.models.tag import Tag

__all__ = [
    "AppSetting",
    "Base",
    "Event",
    "FaceEmbedding",
    "FaceImport",
    "MergeDismissal",
    "Nickname",
    "Person",
    "PersonExternalId",
    "PersonCooccurrence",
    "PersonEmbedding",
    "Photo",
    "PhotoPerson",
    "Tag",
    "event_persons",
    "person_tags",
]
