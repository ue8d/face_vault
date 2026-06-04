"""ベクトルインデックス。FAISS（あれば）/ numpy ブルートフォース（フォールバック）。

両バックエンド共通IF。FAISS未導入のローカルでも同一動作で検証可能。
コサイン類似 = 正規化ベクトルの内積。id = person_embeddings.id。
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from app.face.embedding import l2_normalize

try:  # pragma: no cover - 環境依存
    import faiss  # type: ignore

    _HAS_FAISS = True
except Exception:  # pragma: no cover
    faiss = None  # type: ignore
    _HAS_FAISS = False


class VectorIndex:
    """人物Embeddingの近傍検索。"""

    def __init__(self, dim: int = 512) -> None:
        self.dim = dim
        self._ids = np.empty((0,), dtype="int64")
        if _HAS_FAISS:
            self._index = faiss.IndexIDMap2(faiss.IndexFlatIP(dim))
        else:
            self._mat = np.empty((0, dim), dtype="float32")

    @property
    def backend(self) -> str:
        return "faiss" if _HAS_FAISS else "numpy"

    @property
    def size(self) -> int:
        return int(self._ids.shape[0])

    def build(self, items: list[tuple[int, np.ndarray]]) -> None:
        """(id, vec) 群から再構築。"""
        self.__init__(self.dim)  # リセット
        if items:
            self.add_many(items)

    def add_many(self, items: list[tuple[int, np.ndarray]]) -> None:
        if not items:
            return
        ids = np.array([i for i, _ in items], dtype="int64")
        vecs = np.vstack([l2_normalize(v) for _, v in items]).astype("float32")
        self._ids = np.concatenate([self._ids, ids])
        if _HAS_FAISS:
            self._index.add_with_ids(vecs, ids)
        else:
            self._mat = np.vstack([self._mat, vecs]) if self._mat.size else vecs

    def add(self, id_: int, vec: np.ndarray) -> None:
        self.add_many([(id_, vec)])

    def search(self, vec: np.ndarray, k: int = 5) -> list[tuple[int, float]]:
        """上位k件 (id, コサイン類似) を類似降順で返す。"""
        if self.size == 0:
            return []
        q = l2_normalize(vec).astype("float32").reshape(1, -1)
        k = min(k, self.size)
        if _HAS_FAISS:
            scores, ids = self._index.search(q, k)
            return [(int(i), float(s)) for i, s in zip(ids[0], scores[0]) if i != -1]
        sims = (self._mat @ q[0])
        top = np.argsort(-sims)[:k]
        return [(int(self._ids[i]), float(sims[i])) for i in top]

    def save(self, path: str | Path) -> None:  # pragma: no cover - I/O
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if _HAS_FAISS:
            faiss.write_index(self._index, str(path))
            np.save(path.with_suffix(".ids.npy"), self._ids)
        else:
            np.savez(path, ids=self._ids, mat=self._mat)

    def load(self, path: str | Path) -> None:  # pragma: no cover - I/O
        path = Path(path)
        if _HAS_FAISS:
            self._index = faiss.read_index(str(path))
            self._ids = np.load(path.with_suffix(".ids.npy"))
        else:
            data = np.load(path if path.suffix == ".npz" else path.with_suffix(".npz"))
            self._ids, self._mat = data["ids"], data["mat"]
