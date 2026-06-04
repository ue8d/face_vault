"""写真エンドポイント。"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.base import get_db
from app.schemas.photo import PhotoFilter, PhotoOut, PhotoUpdate
from app.services.photo_service import PhotoService

settings = get_settings()

router = APIRouter()


def _service(db: Session = Depends(get_db)) -> PhotoService:
    return PhotoService(db)


@router.post("/upload", response_model=PhotoOut, status_code=status.HTTP_201_CREATED)
async def upload_photo(
    file: UploadFile = File(...),
    memo: str | None = Form(default=None),
    event_id: int | None = Form(default=None),
    taken_at: datetime | None = Form(default=None),
    svc: PhotoService = Depends(_service),
):
    """写真アップロード → 保存 + メタ登録。

    顔検出/Embedding/照合は次フェーズ（FaceService）。
    """
    content = await file.read()
    return svc.save_upload(
        content=content,
        filename=file.filename or "upload.jpg",
        memo=memo,
        event_id=event_id,
        taken_at=taken_at,
    )


@router.get("", response_model=list[PhotoOut])
def list_photos(
    person_id: int | None = None,
    event_id: int | None = None,
    event_name: str | None = None,
    tag: str | None = None,
    year: int | None = None,
    month: int | None = None,
    limit: int = 100,
    offset: int = 0,
    svc: PhotoService = Depends(_service),
) -> list:
    f = PhotoFilter(
        person_id=person_id,
        event_id=event_id,
        event_name=event_name,
        tag=tag,
        year=year,
        month=month,
    )
    return svc.search(f, limit=limit, offset=offset)


@router.get("/count")
def count_photos(svc: PhotoService = Depends(_service)) -> dict:
    return {"count": svc.count()}


@router.get("/{photo_id}", response_model=PhotoOut)
def get_photo(photo_id: int, svc: PhotoService = Depends(_service)):
    photo = svc.get(photo_id)
    if photo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "photo not found")
    return photo


@router.patch("/{photo_id}", response_model=PhotoOut)
def update_photo(photo_id: int, data: PhotoUpdate, svc: PhotoService = Depends(_service)):
    photo = svc.get(photo_id)
    if photo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "photo not found")
    return svc.update(photo, data)


@router.delete("/{photo_id}")
def delete_photo(photo_id: int, svc: PhotoService = Depends(_service)) -> Response:
    """写真を削除（実体ファイル + 顔リンク + 由来ベクトル + 共起を整理）。"""
    photo = svc.get(photo_id)
    if photo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "photo not found")
    svc.delete(photo)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{photo_id}/reprocess", response_model=PhotoOut)
def reprocess_photo(photo_id: int, svc: PhotoService = Depends(_service)):
    photo = svc.get(photo_id)
    if photo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "photo not found")
    try:
        return svc.reprocess(photo)
    except FileNotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "file missing") from e
    except (ImportError, ModuleNotFoundError) as e:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "face runtime unavailable"
        ) from e


@router.get("/{photo_id}/raw")
def get_photo_raw(photo_id: int, svc: PhotoService = Depends(_service)):
    """写真の実体画像を返す。"""
    photo = svc.get(photo_id)
    if photo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "photo not found")
    fpath = Path(settings.photo_storage_dir) / photo.path
    if not fpath.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "file missing")
    return FileResponse(fpath)


@router.get("/{photo_id}/faces/{link_id}/crop")
def get_face_crop(photo_id: int, link_id: int, svc: PhotoService = Depends(_service)):
    """検出顔の切り抜き（bbox + 余白）を返す。確認キューの表示用。"""
    from io import BytesIO

    from fastapi import Response
    from PIL import Image

    from app.models.photo_person import PhotoPerson

    link = svc.db.get(PhotoPerson, link_id)
    if link is None or link.photo_id != photo_id or not link.bbox:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "face not found")
    photo = svc.get(photo_id)
    fpath = Path(settings.photo_storage_dir) / photo.path
    if not fpath.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "file missing")
    try:
        x, y, w, h = (int(v) for v in link.bbox.split(","))
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "bad bbox") from e

    img = Image.open(fpath).convert("RGB")
    pad = int(max(w, h) * 0.4)
    box = (
        max(0, x - pad),
        max(0, y - pad),
        min(img.width, x + w + pad),
        min(img.height, y + h + pad),
    )
    crop = img.crop(box)
    buf = BytesIO()
    crop.save(buf, "JPEG", quality=85)
    return Response(content=buf.getvalue(), media_type="image/jpeg")
