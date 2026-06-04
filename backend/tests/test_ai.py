"""AIプロバイダ抽象化。キー未設定→NotImplementedError、プロンプト生成。"""
from __future__ import annotations

import pytest

from app.ai.base import PersonContext, build_user_prompt, get_provider


def _ctx() -> PersonContext:
    return PersonContext(
        name="山田太郎",
        nicknames=["タロ", "やまちゃん"],
        relation="大学の友人",
        memo="サークル仲間",
        first_seen="2023-03-01",
        last_seen="2026-05-01",
        photo_count=12,
        frequent_companions=["田中", "鈴木"],
        related_events=["GW飲み会"],
        event_memos=["渋谷"],
    )


def test_build_prompt_includes_nicknames() -> None:
    p = build_user_prompt(_ctx())
    assert "タロ" in p and "やまちゃん" in p
    assert "大学の友人" in p
    assert "田中" in p


@pytest.mark.parametrize("name", ["openai", "anthropic", "gemini"])
def test_provider_without_key_raises(name: str) -> None:
    # キー未設定 → NotImplementedError（→ 呼び出し側はテンプレ回答にフォールバック）
    with pytest.raises(NotImplementedError):
        get_provider(name, api_key=None, model="m", max_tokens=10)


def test_unknown_provider_raises() -> None:
    with pytest.raises(NotImplementedError):
        get_provider("nonsense", api_key="k", model="m", max_tokens=10)
