"""Anthropic (Claude) プロバイダ。"""
from __future__ import annotations

import anyio

from app.ai.base import SYSTEM_PROMPT, AIProvider, PersonContext, build_user_prompt


class AnthropicProvider(AIProvider):
    def __init__(self, *, api_key: str, model: str, max_tokens: int) -> None:
        try:
            from anthropic import Anthropic
        except ImportError as e:  # pragma: no cover
            raise NotImplementedError("anthropic SDK 未導入") from e
        self._client = Anthropic(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens

    async def answer_who_is_this(self, ctx: PersonContext) -> str:
        def _call() -> str:
            msg = self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": build_user_prompt(ctx)}],
            )
            return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")

        return await anyio.to_thread.run_sync(_call)
