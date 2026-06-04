"""Face01 / JAPANESE FACE v1 ONNX embedder.

The upstream FACE01 implementation uses:
5-point face alignment, 224x224 RGB, ToTensor, ImageNet normalization, ONNX
inference, and cosine comparison around threshold 0.4.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from app.face.embedder import FACE01

_MEAN = np.array([0.485, 0.456, 0.406], dtype="float32")
_STD = np.array([0.229, 0.224, 0.225], dtype="float32")
_DST_5PTS_112 = np.array(
    [
        [38.2946, 51.6963],
        [73.5318, 51.5014],
        [56.0252, 71.7366],
        [41.5493, 92.3655],
        [70.7299, 92.2041],
    ],
    dtype="float32",
)


class Face01Embedder:
    """onnxruntime wrapper for JAPANESE_FACE_V1 / efficientnetv2_arcface."""

    model_key = FACE01

    def __init__(self, model_path: str | None = None) -> None:
        from app.core.config import get_settings

        s = get_settings()
        self._path = model_path or s.face01_model_path
        self._size = int(getattr(s, "face01_input_size", 224))
        self._session = None
        self._input_name = ""
        self._dim = 512

    @property
    def dim(self) -> int:
        self._ensure()
        return self._dim

    def _ensure(self) -> None:
        if self._session is not None:
            return
        if not self._path or not Path(self._path).exists():
            raise FileNotFoundError(self._path)

        import onnxruntime as ort

        self._session = ort.InferenceSession(
            self._path, providers=["CPUExecutionProvider"]
        )
        self._input_name = self._session.get_inputs()[0].name
        out_shape = self._session.get_outputs()[0].shape
        last = out_shape[-1] if out_shape else None
        if isinstance(last, int) and last > 0:
            self._dim = last

    def _crop_with_padding(
        self, img_bgr: np.ndarray, bbox: tuple[int, int, int, int]
    ) -> np.ndarray:
        x, y, w, h = (int(v) for v in bbox)
        pad = int(round(max(w, h) * 0.1))
        height, width = img_bgr.shape[:2]
        x0, y0 = max(0, x - pad), max(0, y - pad)
        x1, y1 = min(width, x + w + pad), min(height, y + h + pad)
        crop = img_bgr[y0:y1, x0:x1]
        return crop if crop.size else img_bgr

    def _align_face(
        self, img_bgr: np.ndarray, landmarks: np.ndarray
    ) -> np.ndarray | None:
        import cv2

        pts = np.asarray(landmarks, dtype="float32")
        if pts.shape[0] < 5 or pts.shape[1] < 2:
            return None
        src = pts[:5, :2]
        dst = _DST_5PTS_112 * (self._size / 112.0)
        matrix, _ = cv2.estimateAffinePartial2D(src, dst, method=cv2.LMEDS)
        if matrix is None:
            return None
        return cv2.warpAffine(
            img_bgr,
            matrix,
            (self._size, self._size),
            flags=cv2.INTER_LINEAR,
            borderValue=0,
        )

    def _preprocess(
        self,
        img_bgr: np.ndarray,
        bbox: tuple[int, int, int, int],
        *,
        landmarks: np.ndarray | None = None,
    ) -> np.ndarray:
        import cv2

        crop = self._align_face(img_bgr, landmarks) if landmarks is not None else None
        if crop is None:
            crop = self._crop_with_padding(img_bgr, bbox)
        crop = cv2.resize(crop, (self._size, self._size))
        rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB).astype("float32") / 255.0
        rgb = (rgb - _MEAN) / _STD
        chw = np.transpose(rgb, (2, 0, 1))[np.newaxis, ...]
        return chw.astype("float32")

    def embed(
        self,
        img_bgr: np.ndarray,
        bbox: tuple[int, int, int, int],
        *,
        landmarks: np.ndarray | None = None,
    ) -> np.ndarray:
        self._ensure()
        inp = self._preprocess(img_bgr, bbox, landmarks=landmarks)
        out = self._session.run(None, {self._input_name: inp})[0][0].astype("float32")  # type: ignore[union-attr]
        norm = float(np.linalg.norm(out))
        return out / norm if norm > 0 else out
