"""OpenAI プロバイダ。"""
from __future__ import annotations

import anyio

from app.ai.base import SYSTEM_PROMPT, AIProvider, PersonContext, build_user_prompt


class OpenAIProvider(AIProvider):
    def __init__(self, *, api_key: str, model: str, max_tokens: int) -> None:
        try:
            from openai import OpenAI
        except ImportError as e:  # pragma: no cover
            raise NotImplementedError("openai SDK 未導入") from e
        self._client = OpenAI(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens

    async def answer_who_is_this(self, ctx: PersonContext) -> str:
        def _call() -> str:
            res = self._client.chat.completions.create(
                model=self._model,
                max_tokens=self._max_tokens,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": build_user_prompt(ctx)},
                ],
            )
            return (res.choices[0].message.content or "").strip()

        return await anyio.to_thread.run_sync(_call)
