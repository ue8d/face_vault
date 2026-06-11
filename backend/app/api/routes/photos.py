"""写真エンドポイント。"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_env_id
from app.core.config import get_settings
from app.db.base import get_db
from app.schemas.photo import (
    PhotoBulkImportResult,
    PhotoFilter,
    PhotoOut,
    PhotoUpdate,
    PhotoUrlImport,
    PhotoUrlsImport,
)
from app.services.photo_service import PhotoService

settings = get_settings()

router = APIRouter()


def _service(
    db: Session = Depends(get_db), env_id: int = Depends(get_env_id)
) -> PhotoService:
    return PhotoService(db, env_id)


def _unscoped_service(db: Session = Depends(get_db)) -> PhotoService:
    """環境ヘッダを送れない <img> 直リンク（raw/crop）用。ID直指定のみ。"""
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
        include_filename_in_memo=True,
    )


@router.post(
    "/upload-bulk",
    response_model=PhotoBulkImportResult,
    status_code=status.HTTP_201_CREATED,
)
async def upload_photos_bulk(
    files: list[UploadFile] = File(...),
    memo: str | None = Form(default=None),
    event_id: int | None = Form(default=None),
    taken_at: datetime | None = Form(default=None),
    svc: PhotoService = Depends(_service),
):
    """複数画像をまとめて保存する。失敗したファイルは errors に残す。"""
    if not files:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "file required")

    created = []
    errors = []
    for index, file in enumerate(files, start=1):
        source = file.filename or f"upload-{index}.jpg"
        try:
            content = await file.read()
            if not content:
                raise ValueError("空のファイル")
            created.append(
                svc.save_upload(
                    content=content,
                    filename=source,
                    memo=memo,
                    event_id=event_id,
                    taken_at=taken_at,
                    include_filename_in_memo=True,
                )
            )
        except Exception as e:  # noqa: BLE001 - 一括取込では1件失敗しても継続
            svc.db.rollback()
            errors.append({"source": source, "detail": str(e)})

    if not created and errors:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, errors[0]["detail"])
    return {"created": created, "errors": errors}


@router.post("/import-url", response_model=PhotoOut, status_code=status.HTTP_201_CREATED)
def import_photo_from_url(data: PhotoUrlImport, svc: PhotoService = Depends(_service)):
    """URLから画像を取得して写真として保存する。"""
    try:
        return svc.save_from_url(
            url=str(data.url),
            memo=data.memo,
            event_id=data.event_id,
            taken_at=data.taken_at,
            include_filename_in_memo=True,
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e


@router.post(
    "/import-urls",
    response_model=PhotoBulkImportResult,
    status_code=status.HTTP_201_CREATED,
)
def import_photos_from_urls(data: PhotoUrlsImport, svc: PhotoService = Depends(_service)):
    """複数URLから画像を取得して写真として保存する。失敗URLは errors に残す。"""
    if not data.urls:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "url required")

    created = []
    errors = []
    for url in data.urls:
        source = str(url)
        try:
            created.append(
                svc.save_from_url(
                    url=source,
                    memo=data.memo,
                    event_id=data.event_id,
                    taken_at=data.taken_at,
                    include_filename_in_memo=True,
                )
            )
        except Exception as e:  # noqa: BLE001 - 一括取込では1件失敗しても継続
            svc.db.rollback()
            errors.append({"source": source, "detail": str(e)})

    if not created and errors:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, errors[0]["detail"])
    return {"created": created, "errors": errors}


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
def get_photo_raw(photo_id: int, svc: PhotoService = Depends(_unscoped_service)):
    """写真の実体画像を返す。"""
    photo = svc.get(photo_id)
    if photo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "photo not found")
    fpath = Path(settings.photo_storage_dir) / photo.path
    if not fpath.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "file missing")
    return FileResponse(fpath)


@router.get("/{photo_id}/faces/{link_id}/crop")
def get_face_crop(photo_id: int, link_id: int, svc: PhotoService = Depends(_unscoped_service)):
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
