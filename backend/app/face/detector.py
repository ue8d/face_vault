"""顔検出器。抽象IF + InsightFace(ArcFace) 遅延ロード実装。

InsightFace/onnxruntime/opencv はインポートが重く環境依存。遅延ロードし、
未導入なら明示エラー。テスト/ローカルは検出器を注入して回避可能。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import numpy as np


@dataclass
class DetectedFace:
    bbox: tuple[int, int, int, int]  # x, y, w, h
    embedding: np.ndarray  # 512次元 float32
    det_score: float = 1.0


@runtime_checkable
class FaceDetector(Protocol):
    def detect(self, image_bytes: bytes) -> list[DetectedFace]: ...


class InsightFaceDetector:
    """InsightFace ArcFace 実装。初回detectでモデル初期化。"""

    def __init__(
        self,
        model_name: str | None = None,
        det_size: int | None = None,
        det_thresh: float | None = None,
    ) -> None:
        from app.core.config import get_settings

        s = get_settings()
        self._model_name = model_name or s.face_model_name
        self._det_size = det_size or s.face_det_size
        self._det_thresh = det_thresh if det_thresh is not None else s.face_det_thresh
        self._app = None

    def _fix_nested_pack(self) -> None:
        """一部パック(antelopev2)は zip が models/<name>/<name>/ にネスト展開され
        FaceAnalysis が検出器を見つけられない既知バグ。onnxを1階層上へフラット化。"""
        import os
        import shutil

        base = os.path.expanduser(f"~/.insightface/models/{self._model_name}")
        nested = os.path.join(base, self._model_name)
        if os.path.isdir(nested):
            for name in os.listdir(nested):
                dst = os.path.join(base, name)
                if not os.path.exists(dst):
                    shutil.move(os.path.join(nested, name), dst)
            try:
                os.rmdir(nested)
            except OSError:
                pass

    def _ensure(self) -> None:
        if self._app is not None:
            return
        from insightface.app import FaceAnalysis  # 遅延

        # FaceAnalysis が __init__ 内でDL→ネスト展開→AssertionError(antelopev2バグ)。
        # 失敗したらフラット化して1回リトライ。
        try:
            app = FaceAnalysis(name=self._model_name)
        except AssertionError:
            self._fix_nested_pack()
            app = FaceAnalysis(name=self._model_name)
        app.prepare(
            ctx_id=0,
            det_size=(self._det_size, self._det_size),
            det_thresh=self._det_thresh,
        )
        self._app = app

    def detect(self, image_bytes: bytes) -> list[DetectedFace]:
        import cv2  # 遅延

        self._ensure()
        arr = np.frombuffer(image_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            return []
        faces = self._app.get(img)  # type: ignore[union-attr]
        out: list[DetectedFace] = []
        for f in faces:
            x1, y1, x2, y2 = (int(v) for v in f.bbox)
            out.append(
                DetectedFace(
                    bbox=(x1, y1, x2 - x1, y2 - y1),
                    embedding=np.asarray(f.normed_embedding, dtype="float32"),
                    det_score=float(getattr(f, "det_score", 1.0)),
                )
            )
        return out


_default: FaceDetector | None = None


def get_detector() -> FaceDetector:
    """既定検出器（InsightFace）のシングルトン。"""
    global _default
    if _default is None:
        _default = InsightFaceDetector()
    return _default
