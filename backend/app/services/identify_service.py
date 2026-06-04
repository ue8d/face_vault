"""「この人誰だっけ？」集計 + 回答生成。

DBから人物文脈を集計し、AI抽象化レイヤーで自然文回答。
AI未設定時はテンプレート回答にフォールバック → ローカル動作確認可能。
"""
from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.base import PersonContext, get_provider
from app.models.event import Event
from app.models.person import Person
from app.models.photo import Photo
from app.models.photo_person import PhotoPerson
from app.services.settings_service import SettingsService

logger = logging.getLogger(__name__)


class IdentifyService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def build_context(self, person: Person) -> PersonContext:
        db = self.db

        # 撮影日時範囲 + 枚数
        photo_ids_subq = (
            select(PhotoPerson.photo_id)
            .where(PhotoPerson.person_id == person.id)
            .subquery()
        )
        first_seen, last_seen, count = db.execute(
            select(
                func.min(Photo.taken_at),
                func.max(Photo.taken_at),
                func.count(Photo.id),
            ).where(Photo.id.in_(select(photo_ids_subq)))
        ).one()

        # よく一緒に写る人物 上位5
        companions = db.execute(
            select(Person.name, func.count().label("c"))
            .join(PhotoPerson, PhotoPerson.person_id == Person.id)
            .where(
                PhotoPerson.photo_id.in_(select(photo_ids_subq)),
                Person.id != person.id,
            )
            .group_by(Person.id, Person.name)
            .order_by(func.count().desc())
            .limit(5)
        ).all()

        # 関連イベント + メモ
        events = db.execute(
            select(Event.name, Event.memo)
            .join(Photo, Photo.event_id == Event.id)
            .where(Photo.id.in_(select(photo_ids_subq)))
            .distinct()
        ).all()

        return PersonContext(
            name=person.name,
            nicknames=[n.name for n in person.nicknames],
            relation=person.relation,
            memo=person.memo,
            first_seen=first_seen.isoformat() if first_seen else None,
            last_seen=last_seen.isoformat() if last_seen else None,
            photo_count=count or 0,
            frequent_companions=[c[0] for c in companions],
            related_events=[e[0] for e in events],
            event_memos=[e[1] for e in events if e[1]],
        )

    async def answer(self, person: Person) -> str:
        ctx = self.build_context(person)
        cfg = SettingsService(self.db)
        provider_name = str(cfg.value("ai_provider") or "anthropic")
        key_attr = f"{provider_name}_api_key"
        model_attr = f"{provider_name}_model"
        try:
            provider = get_provider(
                provider_name,
                api_key=cfg.value(key_attr),
                model=str(cfg.value(model_attr) or ""),
                max_tokens=int(cfg.value("ai_max_tokens") or 512),
            )
            return await provider.answer_who_is_this(ctx)
        except NotImplementedError:
            return _template_answer(ctx)  # キー未設定/SDK未導入
        except Exception:  # noqa: BLE001 - API障害でも回答は返す
            logger.warning("AI provider failed, fallback to template", exc_info=True)
            return _template_answer(ctx)


def _template_answer(ctx: PersonContext) -> str:
    """AI未設定時のフォールバック日本語回答。"""
    parts = [f"この人は{ctx.name}さんです。"]
    if ctx.nicknames:
        parts.append("ニックネームは" + "、".join(ctx.nicknames) + "。")
    if ctx.relation:
        parts.append(f"{ctx.relation}として登録されています。")
    if ctx.memo:
        parts.append(ctx.memo)
    if ctx.first_seen:
        parts.append(f"初回の記録は{ctx.first_seen[:7]}です。")
    if ctx.last_seen:
        parts.append(f"最近の記録は{ctx.last_seen[:7]}です。")
    parts.append(f"写真は全{ctx.photo_count}枚。")
    if ctx.frequent_companions:
        parts.append("よく一緒に写るのは" + "、".join(ctx.frequent_companions) + "さんです。")
    if ctx.related_events:
        parts.append("関連イベント: " + "、".join(ctx.related_events) + "。")
    return "\n".join(parts)
