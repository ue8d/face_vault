"""Gemini プロバイダ（google-genai SDK）。"""
from __future__ import annotations

import anyio

from app.ai.base import SYSTEM_PROMPT, AIProvider, PersonContext, build_user_prompt


class GeminiProvider(AIProvider):
    def __init__(self, *, api_key: str, model: str, max_tokens: int) -> None:
        try:
            from google import genai
        except ImportError as e:  # pragma: no cover
            raise NotImplementedError("google-genai SDK 未導入") from e
        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens

    async def answer_who_is_this(self, ctx: PersonContext) -> str:
        from google.genai import types

        def _call() -> str:
            res = self._client.models.generate_content(
                model=self._model,
                contents=build_user_prompt(ctx),
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    max_output_tokens=self._max_tokens,
                ),
            )
            return (res.text or "").strip()

        return await anyio.to_thread.run_sync(_call)
