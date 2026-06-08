"""外部API顔判定エンドポイントのテスト（顔ランタイム無しでも緑）。

認証・一覧・削除はランタイム非依存で検証する。実際の顔判定（detect）は
ランタイム導入環境でのみ動作するため、ここでは認証ゲートまでを確認する。
"""
from __future__ import annotations

import io

from fastapi.testclient import TestClient


def _img() -> dict:
    return {"file": ("a.jpg", io.BytesIO(b"fakejpegbytes"), "image/jpeg")}


def _set_api_key(client: TestClient, key: str) -> None:
    r = client.put("/settings", json={"values": {"api_key": key}})
    assert r.status_code == 200


def test_list_empty(client: TestClient) -> None:
    r = client.get("/api-queries")
    assert r.status_code == 200
    assert r.json() == []


def test_delete_missing_returns_404(client: TestClient) -> None:
    r = client.delete("/api-queries/999")
    assert r.status_code == 404


def test_identify_without_key_setting_is_disabled(client: TestClient) -> None:
    """api_key 未設定ならエンドポイント無効（503）。"""
    r = client.post("/api/identify", files=_img())
    assert r.status_code == 503


def test_identify_wrong_key_rejected(client: TestClient) -> None:
    _set_api_key(client, "secret-key")
    r = client.post("/api/identify", files=_img(), headers={"X-API-Key": "wrong"})
    assert r.status_code == 401


def test_identify_missing_key_header_rejected(client: TestClient) -> None:
    _set_api_key(client, "secret-key")
    r = client.post("/api/identify", files=_img())
    assert r.status_code == 401


def test_storage_dir_honors_db_override(db) -> None:
    """api_storage_dir のDB設定変更がサービスの保存先に反映される。"""
    from pathlib import Path

    from app.services.api_query_service import ApiQueryService
    from app.services.settings_service import SettingsService

    SettingsService(db).update({"api_storage_dir": "/tmp/custom_api_photos"})
    assert ApiQueryService(db).storage == Path("/tmp/custom_api_photos")
