"""FastAPI エントリポイント。OpenAPI自動生成。"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.db.base import Base, SessionLocal, engine

settings = get_settings()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ローカル(sqlite)は起動時テーブル自動作成。本番(Postgres)はentrypoint/Alembic。
    if settings.database_url.startswith("sqlite"):
        import app.models  # noqa: F401  全モデル登録

        Base.metadata.create_all(bind=engine)

    # 顔ベクトルインデックス(FAISS/numpy)を person_embeddings から環境別に構築。
    # DB が正本。再起動毎に再構築 → 常に整合。/faces/reindex でも再構築可。
    from app.face.registry import get_index
    from app.models.environment import Environment
    from app.services.environment_service import ensure_default_environment
    from app.services.face_service import FaceService

    db = SessionLocal()
    try:
        ensure_default_environment(db)
        from sqlalchemy import select

        for env in db.scalars(select(Environment)).all():
            index = get_index(env_id=env.id)
            n = FaceService(db, index, env_id=env.id).rebuild_index()
            logger.info(
                "vector index built: env=%s backend=%s size=%d",
                env.id, index.backend, n,
            )
    except Exception:  # noqa: BLE001 - 構築失敗でもAPI起動は継続（reindexで復旧可）
        logger.warning("vector index build skipped", exc_info=True)
    finally:
        db.close()

    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="個人向け写真記憶アシスタント API",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}
