"""プロセス共有 VectorIndex シングルトン（モデル別）。

各モデル（insightface / face01 ...）は別空間 → model_key ごとに独立した index。
起動時 or 初回利用で DB から構築。テストは reset_index() で初期化。
"""
from __future__ import annotations

from app.core.config import get_settings
from app.face.embedder import FACE01, INSIGHTFACE
from app.face.index import VectorIndex

settings = get_settings()

_indexes: dict[str, VectorIndex] = {}


def _dim_for(model_key: str) -> int:
    if model_key == FACE01:
        return int(settings.face01_dim)
    return int(settings.face_embedding_dim)


def get_index(model_key: str = INSIGHTFACE) -> VectorIndex:
    idx = _indexes.get(model_key)
    if idx is None:
        idx = VectorIndex(dim=_dim_for(model_key))
        _indexes[model_key] = idx
    return idx


def reset_index() -> None:
    _indexes.clear()
