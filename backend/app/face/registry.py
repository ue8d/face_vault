"""プロセス共有 VectorIndex シングルトン。

起動時 or 初回利用で DB から構築。テストは reset_index() で初期化。
"""
from __future__ import annotations

from app.core.config import get_settings
from app.face.index import VectorIndex

settings = get_settings()

_index: VectorIndex | None = None


def get_index() -> VectorIndex:
    global _index
    if _index is None:
        _index = VectorIndex(dim=settings.face_embedding_dim)
    return _index


def reset_index() -> None:
    global _index
    _index = None
