"""顔エンドポイント。再インデックス・候補照合・手動確定・人物顔登録。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.face.registry import get_index
from app.models.photo_person import PhotoPerson
from app.schemas.face import (
    CandidateOut,
    ConfirmFaceRequest,
    PhotoPersonOut,
    ReindexResponse,
)
from app.services.face_service import FaceService

router = APIRouter()


def _face_service(db: Session = Depends(get_db)) -> FaceService:
    return FaceService(db, get_index())


@router.post("/faces/reindex", response_model=ReindexResponse)
def reindex(svc: FaceService = Depends(_face_service)):
    """person_embeddings から VectorIndex を再構築。"""
    size = svc.rebuild_index()
    return ReindexResponse(backend=svc.index.backend, size=size)


@router.patch("/faces/links/{link_id}", response_model=PhotoPersonOut)
def confirm_face(
    link_id: int, req: ConfirmFaceRequest, svc: FaceService = Depends(_face_service)
):
    """検出顔(photo_person)を人物に確定。"""
    link = svc.db.get(PhotoPerson, link_id)
    if link is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "face link not found")
    try:
        return svc.confirm_face(link, req.person_id)
    except ValueError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from e


@router.delete("/faces/links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_face_link(link_id: int, svc: FaceService = Depends(_face_service)) -> Response:
    """検出顔リンクを削除（誤検出/重複の対象外化）。割当済みなら共起も減算。"""
    link = svc.db.get(PhotoPerson, link_id)
    if link is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "face link not found")
    if link.person_id is not None:
        from app.services.cooccurrence_service import CooccurrenceService

        others = svc.db.execute(
            select(PhotoPerson.person_id).where(
                PhotoPerson.photo_id == link.photo_id,
                PhotoPerson.person_id.isnot(None),
                PhotoPerson.id != link.id,
            )
        ).scalars().all()
        for o in set(others):
            CooccurrenceService(svc.db).bump_pairs([link.person_id, o], delta=-1)
    svc.db.delete(link)
    svc.db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/persons/{person_id}/faces", response_model=list[CandidateOut])
async def register_person_face(
    person_id: int,
    file: UploadFile = File(...),
    svc: FaceService = Depends(_face_service),
):
    """人物の参照顔写真を登録（検出器で1顔抽出→Embedding登録）。

    元画像も保存し、その写真を本人の確定済み顔として紐付ける。
    顔認識ランタイム未導入時は 503。
    """
    content = await file.read()
    try:
        from app.face.detector import get_detector

        faces = get_detector().detect(content)
    except (ImportError, ModuleNotFoundError) as e:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "face runtime unavailable"
        ) from e
    if not faces:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "no face detected")

    from app.services.photo_service import PhotoService

    photo = PhotoService(svc.db).store_image(
        content=content,
        filename=file.filename or "reference.jpg",
        memo=f"参照顔登録 (person #{person_id})",
    )
    svc.register_reference(person_id, faces[0], photo.id)
    svc.db.commit()
    return []
