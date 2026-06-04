"""動的設定（DB管理 + Web更新）。"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.services.settings_service import SettingsService


def test_list_settings_defaults(client: TestClient) -> None:
    items = client.get("/settings").json()
    keys = {i["key"] for i in items}
    assert {
        "ai_provider",
        "anthropic_api_key",
        "match_threshold",
        "online_learning_enabled",
    } <= keys
    ai = next(i for i in items if i["key"] == "ai_provider")
    assert ai["value"] == "anthropic"  # env/デフォルト
    assert ai["source"] == "env/default"


def test_update_and_override(client: TestClient) -> None:
    r = client.put("/settings", json={"values": {"ai_provider": "openai"}})
    assert r.status_code == 200
    ai = next(i for i in r.json() if i["key"] == "ai_provider")
    assert ai["value"] == "openai"
    assert ai["source"] == "db"


def test_secret_masked_but_flagged(client: TestClient) -> None:
    client.put("/settings", json={"values": {"anthropic_api_key": "sk-test"}})
    sec = next(i for i in client.get("/settings").json() if i["key"] == "anthropic_api_key")
    assert sec["value"] == ""  # マスク
    assert sec["is_set"] is True


def test_clear_reverts_to_default(client: TestClient) -> None:
    client.put("/settings", json={"values": {"ai_provider": "gemini"}})
    client.put("/settings", json={"values": {"ai_provider": ""}})  # 解除
    ai = next(i for i in client.get("/settings").json() if i["key"] == "ai_provider")
    assert ai["value"] == "anthropic" and ai["source"] == "env/default"


def test_typed_value(db) -> None:
    svc = SettingsService(db)
    svc.update({
        "match_threshold": "0.5",
        "ai_max_tokens": "256",
        "online_learning_enabled": "false",
    })
    assert isinstance(svc.value("match_threshold"), float) and svc.value("match_threshold") == 0.5
    assert isinstance(svc.value("ai_max_tokens"), int) and svc.value("ai_max_tokens") == 256
    assert svc.value("online_learning_enabled") is False
