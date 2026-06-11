"""環境（テナント）サービス。CRUD + 配下データの完全削除。

削除は環境配下の 人物/写真/イベント/タグ/API受信ログ と派生データ
（embeddings/共起/却下記録/取込キュー/実体ファイル）を明示的に消す。
SQLite は FK カスケードが効かない（PRAGMA無効）ため DB任せにしない。
"""
from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.api_query import ApiQuery
from app.models.associations import event_persons, person_tags
from app.models.collect_source import CollectSource
from app.models.collected_url import CollectedUrl
from app.models.cooccurrence import PersonCooccurrence
from app.models.environment import DEFAULT_ENVIRONMENT_NAME, Environment
from app.models.event import Event
from app.models.face_embedding import FaceEmbedding
from app.models.face_import import FaceImport
from app.models.merge_dismissal import MergeDismissal
from app.models.nickname import Nickname
from app.models.person import Person
from app.models.person_embedding import PersonEmbedding
from app.models.person_external_id import PersonExternalId
from app.models.photo import Photo
from app.models.photo_person import PhotoPerson
from app.models.tag import Tag

settings = get_settings()
logger = logging.getLogger(__name__)


def ensure_default_environment(db: Session) -> Environment:
    """環境が1つも無ければ default を作成して返す（冪等）。"""
    env = db.scalars(select(Environment).order_by(Environment.id).limit(1)).first()
    if env is not None:
        return env
    env = Environment(name=DEFAULT_ENVIRONMENT_NAME)
    db.add(env)
    db.commit()
    db.refresh(env)
    return env


class EnvironmentService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list(self) -> list[dict]:
        envs = list(self.db.scalars(select(Environment).order_by(Environment.id)).all())
        person_counts = dict(
            self.db.execute(
                select(Person.environment_id, func.count(Person.id)).group_by(
                    Person.environment_id
                )
            ).all()
        )
        photo_counts = dict(
            self.db.execute(
                select(Photo.environment_id, func.count(Photo.id)).group_by(
                    Photo.environment_id
                )
            ).all()
        )
        return [
            {
                "id": e.id,
                "name": e.name,
                "created_at": e.created_at,
                "person_count": person_counts.get(e.id, 0),
                "photo_count": photo_counts.get(e.id, 0),
            }
            for e in envs
        ]

    def get(self, env_id: int) -> Environment | None:
        return self.db.get(Environment, env_id)

    def create(self, name: str) -> Environment:
        name = name.strip()
        if not name:
            raise ValueError("環境名は必須です")
        if self.db.scalar(select(Environment.id).where(Environment.name == name)):
            raise ValueError("同名の環境が既に存在します")
        env = Environment(name=name)
        self.db.add(env)
        self.db.commit()
        self.db.refresh(env)
        return env

    def rename(self, env: Environment, name: str) -> Environment:
        name = name.strip()
        if not name:
            raise ValueError("環境名は必須です")
        dup = self.db.scalar(
            select(Environment.id).where(Environment.name == name, Environment.id != env.id)
        )
        if dup:
            raise ValueError("同名の環境が既に存在します")
        env.name = name
        self.db.commit()
        self.db.refresh(env)
        return env

    def delete(self, env: Environment) -> None:
        """環境と配下データを全削除。最後の1環境は削除不可。"""
        total = self.db.scalar(select(func.count(Environment.id))) or 0
        if total <= 1:
            raise ValueError("最後の環境は削除できません")

        env_id = env.id
        person_ids = select(Person.id).where(Person.environment_id == env_id)
        photo_ids = select(Photo.id).where(Photo.environment_id == env_id)
        link_ids = select(PhotoPerson.id).where(PhotoPerson.photo_id.in_(photo_ids))

        # 実体ファイルのパスを先に収集（行削除後は辿れない）
        photo_paths = list(
            self.db.scalars(select(Photo.path).where(Photo.environment_id == env_id))
        )
        api_paths = list(
            self.db.scalars(select(ApiQuery.path).where(ApiQuery.environment_id == env_id))
        )

        # 子 → 親 の順に明示削除
        self.db.execute(
            delete(FaceEmbedding).where(FaceEmbedding.photo_person_id.in_(link_ids))
        )
        self.db.execute(delete(PhotoPerson).where(PhotoPerson.photo_id.in_(photo_ids)))
        self.db.execute(
            delete(PersonEmbedding).where(PersonEmbedding.person_id.in_(person_ids))
        )
        self.db.execute(delete(FaceImport).where(FaceImport.person_id.in_(person_ids)))
        self.db.execute(
            delete(MergeDismissal).where(
                MergeDismissal.person_a_id.in_(person_ids)
                | MergeDismissal.person_b_id.in_(person_ids)
            )
        )
        self.db.execute(
            delete(PersonCooccurrence).where(
                PersonCooccurrence.person_a_id.in_(person_ids)
                | PersonCooccurrence.person_b_id.in_(person_ids)
            )
        )
        self.db.execute(delete(Nickname).where(Nickname.person_id.in_(person_ids)))
        self.db.execute(
            delete(PersonExternalId).where(PersonExternalId.environment_id == env_id)
        )
        self.db.execute(delete(person_tags).where(person_tags.c.person_id.in_(person_ids)))
        self.db.execute(delete(event_persons).where(event_persons.c.person_id.in_(person_ids)))
        self.db.execute(delete(CollectedUrl).where(CollectedUrl.environment_id == env_id))
        self.db.execute(delete(CollectSource).where(CollectSource.environment_id == env_id))
        self.db.execute(delete(ApiQuery).where(ApiQuery.environment_id == env_id))
        self.db.execute(delete(Photo).where(Photo.environment_id == env_id))
        self.db.execute(delete(Person).where(Person.environment_id == env_id))
        self.db.execute(delete(Event).where(Event.environment_id == env_id))
        self.db.execute(delete(Tag).where(Tag.environment_id == env_id))
        self.db.delete(env)
        self.db.commit()

        # ベクトルインデックス破棄
        from app.face.registry import drop_env_indexes

        drop_env_indexes(env_id)

        # 実体ファイル削除（ベストエフォート）
        from app.services.settings_service import SettingsService

        cfg = SettingsService(self.db)
        photo_dir = Path(str(cfg.value("photo_storage_dir") or settings.photo_storage_dir))
        api_dir = Path(str(cfg.value("api_storage_dir") or settings.api_storage_dir))
        for base, rels in ((photo_dir, photo_paths), (api_dir, api_paths)):
            for rel in rels:
                try:
                    (base / rel).unlink(missing_ok=True)
                except OSError:
                    logger.warning("failed to remove file %s", base / rel, exc_info=True)
