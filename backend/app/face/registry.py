"""プロセス共有 VectorIndex シングルトン（モデル別 × 環境別）。

各モデル（insightface / face01 ...）は別空間 → model_key ごとに独立した index。
さらに環境（テナント）ごとに分離し、環境間の照合汚染を防ぐ。
起動時 or 初回利用で DB から構築。テストは reset_index() で初期化。
"""
from __future__ import annotations

from app.core.config import get_settings
from app.face.embedder import FACE01, INSIGHTFACE
from app.face.index import VectorIndex

settings = get_settings()

# key = (model_key, env_id)。env_id=None は環境非依存（テスト/レガシー呼び出し）。
_indexes: dict[tuple[str, int | None], VectorIndex] = {}


def _dim_for(model_key: str) -> int:
    if model_key == FACE01:
        return int(settings.face01_dim)
    return int(settings.face_embedding_dim)


def get_index(model_key: str = INSIGHTFACE, env_id: int | None = None) -> VectorIndex:
    key = (model_key, env_id)
    idx = _indexes.get(key)
    if idx is None:
        idx = VectorIndex(dim=_dim_for(model_key))
        _indexes[key] = idx
    return idx


def drop_env_indexes(env_id: int) -> None:
    """環境削除時に該当環境の index を破棄。"""
    for key in [k for k in _indexes if k[1] == env_id]:
        del _indexes[key]


def reset_index() -> None:
    _indexes.clear()
