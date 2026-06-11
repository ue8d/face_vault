"""テーブル作成（コンテナ起動時）。本番はAlembic移行に置換可。

`python -m app.db_init` で実行。全モデルmetadataから create_all。
冪等。
"""
from __future__ import annotations

import app.models  # noqa: F401  全モデル登録
from app.db.base import Base, SessionLocal, engine


def main() -> None:
    Base.metadata.create_all(bind=engine)
    from app.services.environment_service import ensure_default_environment

    db = SessionLocal()
    try:
        ensure_default_environment(db)
    finally:
        db.close()
    print("[db_init] tables ensured")


if __name__ == "__main__":
    main()
