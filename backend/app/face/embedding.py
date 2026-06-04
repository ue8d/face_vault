"""Embedding ユーティリティ。bytes ⇔ numpy、正規化、コサイン類似。

ArcFace 512次元 float32。DB保存はリトルエンディアン float32 バイト列。
"""
from __future__ import annotations

import numpy as np


def to_bytes(vec: np.ndarray) -> bytes:
    return np.asarray(vec, dtype="<f4").tobytes()


def from_bytes(buf: bytes) -> np.ndarray:
    return np.frombuffer(buf, dtype="<f4").copy()


def l2_normalize(vec: np.ndarray) -> np.ndarray:
    vec = np.asarray(vec, dtype="float32")
    norm = np.linalg.norm(vec)
    return vec / norm if norm > 0 else vec


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(l2_normalize(a), l2_normalize(b)))
