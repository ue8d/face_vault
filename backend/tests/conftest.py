"""テスト基盤。環境変数を先に設定してから app を import。"""
from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator

# app import 前に環境変数確定（sqlite + 一時ストレージ）
_TMP = tempfile.mkdtemp(prefix="face_vault_test_")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_TMP, 'test.db')}"
os.environ["PHOTO_STORAGE_DIR"] = os.path.join(_TMP, "photos")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import app.models  # noqa: E402,F401  全モデル登録
from app.db.base import Base, SessionLocal, engine  # noqa: E402
from app.face.registry import reset_index  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture
def client() -> Iterator[TestClient]:
    reset_index()
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(bind=engine)
    reset_index()


@pytest.fixture
def db() -> Iterator["object"]:
    reset_index()
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        reset_index()
