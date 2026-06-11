"""タグ リポジトリ。"""
from __future__ import annotations

from sqlalchemy import select

from app.models.tag import Tag
from app.repositories.base import BaseRepository


class TagRepository(BaseRepository[Tag]):
    model = Tag

    def get_by_name(self, name: str) -> Tag | None:
        return self.db.scalar(self._scoped(select(Tag).where(Tag.name == name)))

    def get_or_create(self, name: str) -> Tag:
        tag = self.get_by_name(name)
        if tag is None:
            tag = Tag(name=name)
            self.add(tag)
        return tag
