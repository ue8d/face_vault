#!/usr/bin/env bash
set -euo pipefail

# DB待機（pg_isready無しでもpsycopg接続リトライ）
echo "[entrypoint] waiting for database..."
python - <<'PY'
import time
from sqlalchemy import text
from app.db.base import engine

for i in range(60):
    try:
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
        print("[entrypoint] database ready")
        break
    except Exception as e:
        if i == 0:
            print(f"[entrypoint] db not ready: {e}")
        time.sleep(1)
else:
    raise SystemExit("[entrypoint] database unreachable")
PY

# テーブル作成（冪等）
python -m app.db_init

exec uvicorn app.main:app --host 0.0.0.0 --port 8017
