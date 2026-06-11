"""写真 リポジトリ。検索条件対応。"""
from __future__ import annotations

from sqlalchemy import exists, extract, select

from app.models.associations import person_tags
from app.models.event import Event
from app.models.person import Person
from app.models.photo import Photo
from app.models.photo_person import PhotoPerson
from app.models.tag import Tag
from app.repositories.base import BaseRepository
from app.schemas.photo import PhotoFilter


class PhotoRepository(BaseRepository[Photo]):
    model = Photo

    def search(self, f: PhotoFilter, *, limit: int = 100, offset: int = 0) -> list[Photo]:
        stmt = self._scoped(select(Photo))
        if f.person_id is not None:
            stmt = stmt.where(
                exists().where(
                    PhotoPerson.photo_id == Photo.id,
                    PhotoPerson.person_id == f.person_id,
                )
            )
        if f.event_id is not None:
            stmt = stmt.where(Photo.event_id == f.event_id)
        if f.event_name:
            stmt = stmt.where(
                exists().where(
                    Event.id == Photo.event_id,
                    Event.name.ilike(f"%{f.event_name}%"),
                )
            )
        if f.tag:
            stmt = stmt.where(
                exists(
                    select(1)
                    .select_from(PhotoPerson)
                    .join(Person, PhotoPerson.person_id == Person.id)
                    .join(person_tags, person_tags.c.person_id == Person.id)
                    .join(Tag, Tag.id == person_tags.c.tag_id)
                    .where(
                        PhotoPerson.photo_id == Photo.id,
                        Tag.name.ilike(f"%{f.tag}%"),
                    )
                )
            )
        if f.year is not None:
            stmt = stmt.where(extract("year", Photo.taken_at) == f.year)
        if f.month is not None:
            stmt = stmt.where(extract("month", Photo.taken_at) == f.month)
        # 登録日時(created_at)降順 — 新規追加が常に先頭。
        # taken_at順だと古いEXIF日時の写真が下位に沈み「追加したのに一覧に出ない」ため。
        stmt = (
            stmt.order_by(Photo.created_at.desc(), Photo.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.scalars(stmt).unique().all())
