"""Embedding model registry for multi-model face recognition."""
from __future__ import annotations

import logging
from typing import Protocol, runtime_checkable

import numpy as np

logger = logging.getLogger(__name__)

INSIGHTFACE = "insightface"
FACE01 = "face01"


@runtime_checkable
class CropEmbedder(Protocol):
    """Model that derives an embedding from an already detected face crop."""

    model_key: str
    dim: int

    def embed(
        self,
        img_bgr: np.ndarray,
        bbox: tuple[int, int, int, int],
        *,
        landmarks: np.ndarray | None = None,
    ) -> np.ndarray:
        """Return an L2-normalized embedding for one detected face."""
        ...


_crop_embedders: list[CropEmbedder] | None = None
_face01_enabled_override: bool | None = None
_face01_model_path_override: str | None = None


def configure_runtime_embedders(
    *, face01_enabled: bool | None = None, face01_model_path: str | None = None
) -> None:
    """Apply DB-backed runtime settings for optional embedders."""
    global _crop_embedders, _face01_enabled_override, _face01_model_path_override
    if (
        face01_enabled == _face01_enabled_override
        and face01_model_path == _face01_model_path_override
    ):
        return
    _face01_enabled_override = face01_enabled
    _face01_model_path_override = face01_model_path
    _crop_embedders = None


def get_crop_embedders() -> list[CropEmbedder]:
    """Return optional embedders enabled for this process."""
    global _crop_embedders
    if _crop_embedders is not None:
        return _crop_embedders

    from app.core.config import get_settings

    s = get_settings()
    face01_enabled = (
        _face01_enabled_override
        if _face01_enabled_override is not None
        else getattr(s, "face01_enabled", False)
    )
    face01_model_path = _face01_model_path_override or getattr(
        s, "face01_model_path", None
    )

    embedders: list[CropEmbedder] = []
    if face01_enabled:
        try:
            from app.face.face01 import Face01Embedder

            embedders.append(Face01Embedder(model_path=face01_model_path))
        except Exception:
            logger.warning("Face01 embedder unavailable; skipping", exc_info=True)

    _crop_embedders = embedders
    return _crop_embedders


def active_model_keys() -> list[str]:
    return [INSIGHTFACE] + [e.model_key for e in get_crop_embedders()]


def reset_embedders() -> None:
    global _crop_embedders
    _crop_embedders = None
