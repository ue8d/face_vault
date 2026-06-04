"""AIプロバイダ抽象化レイヤー。OpenAI/Anthropic/Gemini を共通IFで切替。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class PersonContext:
    """identify-person 回答生成の文脈。"""

    name: str
    relation: str | None
    memo: str | None
    first_seen: str | None
    last_seen: str | None
    photo_count: int
    frequent_companions: list[str]
    related_events: list[str]
    event_memos: list[str]
    nicknames: list[str] = field(default_factory=list)


SYSTEM_PROMPT = (
    "あなたは個人の写真記憶アシスタント。与えられた人物データだけを根拠に、"
    "『この人は誰か』を日本語で簡潔・自然に説明する。"
    "データに無い事実は創作しない。3〜5文程度。敬体。"
)


def build_user_prompt(ctx: PersonContext) -> str:
    """PersonContext を箇条書きプロンプト化。"""
    lines = [f"名前: {ctx.name}"]
    if ctx.nicknames:
        lines.append("ニックネーム: " + "、".join(ctx.nicknames))
    if ctx.relation:
        lines.append(f"関係性: {ctx.relation}")
    if ctx.memo:
        lines.append(f"メモ: {ctx.memo}")
    if ctx.first_seen:
        lines.append(f"初回撮影: {ctx.first_seen}")
    if ctx.last_seen:
        lines.append(f"最終撮影: {ctx.last_seen}")
    lines.append(f"写真枚数: {ctx.photo_count}")
    if ctx.frequent_companions:
        lines.append("よく一緒に写る人物: " + "、".join(ctx.frequent_companions))
    if ctx.related_events:
        lines.append("関連イベント: " + "、".join(ctx.related_events))
    if ctx.event_memos:
        lines.append("イベントメモ: " + "、".join(ctx.event_memos))
    return "以下の人物について説明してください。\n\n" + "\n".join(lines)


class AIProvider(ABC):
    """全プロバイダ共通インターフェース。"""

    @abstractmethod
    async def answer_who_is_this(self, ctx: PersonContext) -> str:
        """人物文脈から自然文回答を生成。"""
        ...


def get_provider(
    name: str, *, api_key: str | None, model: str, max_tokens: int
) -> AIProvider:
    """プロバイダ実装を解決（ファクトリ）。値は呼び出し側(動的設定)から注入。

    APIキー未設定/SDK未導入は NotImplementedError → 呼び出し側でテンプレ回答に
    フォールバック。
    """
    key = name.lower().strip()
    if not api_key:
        raise NotImplementedError(f"{name} APIキー 未設定")
    if key == "openai":
        from app.ai.openai_provider import OpenAIProvider

        return OpenAIProvider(api_key=api_key, model=model, max_tokens=max_tokens)
    if key == "anthropic":
        from app.ai.anthropic_provider import AnthropicProvider

        return AnthropicProvider(api_key=api_key, model=model, max_tokens=max_tokens)
    if key == "gemini":
        from app.ai.gemini_provider import GeminiProvider

        return GeminiProvider(api_key=api_key, model=model, max_tokens=max_tokens)
    raise NotImplementedError(f"unknown AI provider: {name}")
