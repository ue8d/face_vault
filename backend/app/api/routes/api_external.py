"""外部API（顔判定のみ・学習なし）+ 受信画像の閲覧/削除エンドポイント。

- POST /api/identify : 外部呼び出し。X-API-Key 認証必須。顔判定のみ（DB学習なし）。
                       受信画像は api_storage_dir へ WebP 保存し api_queries に記録。
- GET  /api-queries           : 受信画像一覧（Web閲覧用）
- GET  /api-queries/{id}/raw  : 受信画像の実体
- DELETE /api-queries/{id}    : 受信画像と記録を削除
"""
from __future__ import annotations

import secrets
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.schemas.api_query import ApiIdentifyResponse, ApiQueryOut
from app.services.api_query_service import ApiQueryService
from app.services.settings_service import SettingsService

router = APIRouter()


def _service(db: Session = Depends(get_db)) -> ApiQueryService:
    return ApiQueryService(db)


def require_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    db: Session = Depends(get_db),
) -> None:
    """X-API-Key を DB設定 api_key と定数時間比較。未設定ならエンドポイント無効。"""
    expected = SettingsService(db).value("api_key")
    if not expected:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "API key 未設定。設定画面で発行してください。",
        )
    if not x_api_key or not secrets.compare_digest(str(x_api_key), str(expected)):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid api key")


@router.post(
    "/api/identify",
    response_model=ApiIdentifyResponse,
    dependencies=[Depends(require_api_key)],
    tags=["external-api"],
)
async def api_identify(
    file: UploadFile = File(...),
    note: str | None = Form(default=None),
    svc: ApiQueryService = Depends(_service),
):
    """外部向け顔判定。検出した各顔に対し既存人物の上位N候補を返す（学習・登録なし）。"""
    content = await file.read()
    if not content:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "empty file")

    top_n = int(SettingsService(svc.db).value("api_identify_top_n") or 5)
    try:
        row = svc.identify(content=content, note=note, top_n=top_n)
    except (ImportError, ModuleNotFoundError) as e:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "face runtime unavailable"
        ) from e

    return ApiIdentifyResponse(
        query_id=row.id,
        faces_detected=row.faces_detected,
        result=row.result,
    )


@router.get("/api-queries", response_model=list[ApiQueryOut], tags=["external-api"])
def list_api_queries(
    limit: int = 100,
    offset: int = 0,
    svc: ApiQueryService = Depends(_service),
) -> list:
    return svc.list(limit=limit, offset=offset)


@router.get("/api-queries/{query_id}/raw", tags=["external-api"])
def get_api_query_raw(query_id: int, svc: ApiQueryService = Depends(_service)):
    row = svc.get(query_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "api query not found")
    fpath: Path = svc.file_path(row)
    if not fpath.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "file missing")
    return FileResponse(fpath)


@router.get("/api-queries/{query_id}/crop", tags=["external-api"])
def get_api_query_crop(query_id: int, svc: ApiQueryService = Depends(_service)):
    """最初の検出顔のbboxで切り抜いた画像を返す（顔未検出時は全体）。プレビュー用。"""
    from io import BytesIO

    from PIL import Image

    row = svc.get(query_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "api query not found")
    fpath: Path = svc.file_path(row)
    if not fpath.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "file missing")

    img = Image.open(fpath).convert("RGB")
    faces = row.result or []
    bbox = faces[0].get("bbox") if faces else None
    if bbox and len(bbox) == 4:
        x, y, w, h = (int(v) for v in bbox)
        pad = int(max(w, h) * 0.4)
        img = img.crop(
            (
                max(0, x - pad),
                max(0, y - pad),
                min(img.width, x + w + pad),
                min(img.height, y + h + pad),
            )
        )
    buf = BytesIO()
    img.save(buf, "JPEG", quality=85)
    return Response(content=buf.getvalue(), media_type="image/jpeg")


@router.delete("/api-queries/{query_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["external-api"])
def delete_api_query(query_id: int, svc: ApiQueryService = Depends(_service)) -> Response:
    row = svc.get(query_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "api query not found")
    svc.delete(row)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
