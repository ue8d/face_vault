"""人物 サービス。タグ解決・トランザクション管理。"""
from __future__ import annotations

import csv
import io

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.event import Event
from app.models.nickname import Nickname
from app.models.person import Person
from app.models.person_external_id import PersonExternalId
from app.repositories.person import PersonRepository
from app.repositories.tag import TagRepository
from app.schemas.person import PersonCreate, PersonImportResult, PersonUpdate


def _clean(names: list[str]) -> list[str]:
    """空白除去・重複排除（順序維持）。"""
    seen: set[str] = set()
    out: list[str] = []
    for n in names:
        s = n.strip()
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out


class PersonService:
    def __init__(self, db: Session, env_id: int | None = None) -> None:
        self.db = db
        self.env_id = env_id
        self.persons = PersonRepository(db, env_id)
        self.tags = TagRepository(db, env_id)

    def list(self, *, q: str | None = None, limit: int = 100, offset: int = 0) -> list[Person]:
        if q:
            return self.persons.search_by_name(q, limit=limit, offset=offset)
        return self.persons.list(limit=limit, offset=offset)

    def count(self, *, q: str | None = None) -> int:
        return self.persons.count(q)

    def get(self, person_id: int) -> Person | None:
        return self.persons.get(person_id)

    def get_event(self, event_id: int) -> Event | None:
        event = self.db.get(Event, event_id)
        if (
            event is not None
            and self.env_id is not None
            and event.environment_id != self.env_id
        ):
            return None
        return event

    def create(self, data: PersonCreate) -> Person:
        person = Person(
            name=data.name,
            relation=data.relation,
            memo=data.memo,
        )
        person.nicknames = [Nickname(name=n) for n in _clean(data.nicknames)]
        person.tags = [self.tags.get_or_create(t) for t in data.tags]
        self.persons.add(person)
        self.db.commit()
        self.db.refresh(person)
        return person

    def update(self, person: Person, data: PersonUpdate) -> Person:
        for field in ("name", "relation", "memo"):
            val = getattr(data, field)
            if val is not None:
                setattr(person, field, val)
        if data.nicknames is not None:
            person.nicknames = [Nickname(name=n) for n in _clean(data.nicknames)]
        if data.tags is not None:
            person.tags = [self.tags.get_or_create(t) for t in data.tags]
        self.db.commit()
        self.db.refresh(person)
        return person

    def import_friend_csv(self, content: str, *, source: str = "friends_csv") -> PersonImportResult:
        text = content.lstrip("\ufeff")
        reader = csv.DictReader(io.StringIO(text))
        required = {"id", "name", "name_type"}
        if reader.fieldnames is None:
            raise ValueError("CSV header is required")
        missing = required - {name.strip() for name in reader.fieldnames}
        if missing:
            raise ValueError("missing columns: " + ", ".join(sorted(missing)))

        has_img = "img_url" in {name.strip() for name in reader.fieldnames}
        grouped: dict[str, dict[str, list[str]]] = {}
        img_urls: dict[str, str] = {}  # external_id -> img_url（最初の非空）
        result = PersonImportResult()
        for row_no, row in enumerate(reader, start=2):
            external_id = (row.get("id") or "").strip()
            name = (row.get("name") or "").strip()
            name_type = (row.get("name_type") or "").strip().lower()
            if not external_id or not name or not name_type:
                result.skipped += 1
                result.errors.append(f"row {row_no}: id, name, and name_type are required")
                continue
            if name_type not in {"main", "alias"}:
                result.skipped += 1
                result.errors.append(f"row {row_no}: unknown name_type '{name_type}'")
                continue
            grouped.setdefault(external_id, {"main": [], "alias": []})[name_type].append(name)
            if has_img and external_id not in img_urls:
                url = (row.get("img_url") or "").strip()
                if url:
                    img_urls[external_id] = url

        for external_id, names in grouped.items():
            mains = _clean(names["main"])
            aliases = _clean(names["alias"])
            if not mains:
                result.skipped += 1
                result.errors.append(f"id {external_id}: main name is required")
                continue

            main = mains[0]
            aliases = _clean([*mains[1:], *aliases])
            aliases = [alias for alias in aliases if alias != main]
            url = img_urls.get(external_id)
            ext_stmt = select(PersonExternalId).where(
                PersonExternalId.source == source,
                PersonExternalId.external_id == external_id,
            )
            if self.env_id is not None:
                ext_stmt = ext_stmt.where(PersonExternalId.environment_id == self.env_id)
            external = self.db.scalar(ext_stmt)
            if external is None:
                person = Person(name=main)
                person.nicknames = [Nickname(name=alias) for alias in aliases]
                self.persons.add(person)
                self.db.flush()
                ext = PersonExternalId(
                    person_id=person.id,
                    source=source,
                    external_id=external_id,
                )
                if self.env_id is not None:
                    ext.environment_id = self.env_id
                self.db.add(ext)
                result.created += 1
                if url and self._enqueue_face(person.id, url):
                    result.face_queued += 1
                continue

            person = external.person
            if url and self._enqueue_face(person.id, url):
                result.face_queued += 1
            existing = [nickname.name for nickname in person.nicknames]
            merged = _clean([*existing, *aliases])
            changed = False
            if person.name != main:
                person.name = main
                changed = True
            if merged != existing:
                person.nicknames = [Nickname(name=alias) for alias in merged]
                changed = True
            if changed:
                result.updated += 1
            else:
                result.skipped += 1

        self.db.commit()
        return result

    def _enqueue_face(self, person_id: int, img_url: str) -> bool:
        """参照顔取込を予約。既にEmbedding有 or 同一予約済みなら何もしない。"""
        from app.models.face_import import FaceImport
        from app.models.person_embedding import PersonEmbedding

        has_emb = self.db.scalar(
            select(PersonEmbedding.id).where(PersonEmbedding.person_id == person_id).limit(1)
        )
        if has_emb is not None:
            return False
        dup = self.db.scalar(
            select(FaceImport.id).where(
                FaceImport.person_id == person_id,
                FaceImport.img_url == img_url,
                FaceImport.status.in_(("pending", "done")),
            )
        )
        if dup is not None:
            return False
        self.db.add(FaceImport(person_id=person_id, img_url=img_url, status="pending"))
        return True

    def add_event(self, person: Person, event: Event) -> Event:
        if all(existing.id != event.id for existing in person.events):
            person.events.append(event)
            self.db.commit()
        self.db.refresh(event)
        return event

    def remove_event(self, person: Person, event: Event) -> None:
        person.events = [existing for existing in person.events if existing.id != event.id]
        self.db.commit()

    def delete(self, person: Person) -> None:
        self.persons.delete(person)
        self.db.commit()
