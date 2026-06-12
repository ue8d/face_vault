"""Face recognition endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_env_id
from app.db.base import get_db
from app.face.registry import get_index
from app.models.person import Person
from app.models.photo_person import PhotoPerson
from app.schemas.face import (
    CandidateOut,
    ConfirmFaceRequest,
    FaceBackfillResponse,
    PhotoPersonOut,
    ReindexResponse,
)
from app.services.face_backfill_service import FaceBackfillService
from app.services.face_service import FaceService

router = APIRouter()


def _face_service(
    db: Session = Depends(get_db), env_id: int = Depends(get_env_id)
) -> FaceService:
    return FaceService(db, get_index(env_id=env_id), env_id=env_id)


def _get_person_scoped(svc: FaceService, person_id: int) -> Person:
    """環境内の人物を取得。存在しない/他環境なら404（FK違反500・環境間ベクトル汚染を防ぐ）。"""
    person = svc.db.get(Person, person_id)
    if person is None or (
        svc.env_id is not None and person.environment_id != svc.env_id
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "person not found")
    return person


def _get_link_scoped(svc: FaceService, link_id: int) -> PhotoPerson:
    """環境内の検出顔リンクを取得。写真の環境が異なる場合も404。"""
    link = svc.db.get(PhotoPerson, link_id)
    if link is None or (
        svc.env_id is not None and link.photo.environment_id != svc.env_id
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "face link not found")
    return link


@router.post("/faces/reindex", response_model=ReindexResponse)
def reindex(svc: FaceService = Depends(_face_service)):
    size = svc.rebuild_index()
    return ReindexResponse(backend=svc.index.backend, size=size)


@router.post("/faces/backfill/face01", response_model=FaceBackfillResponse)
def backfill_face01(
    limit: int | None = None,
    svc: FaceService = Depends(_face_service),
):
    try:
        result = FaceBackfillService(svc.db, env_id=svc.env_id).backfill_face01(limit=limit)
        svc.db.commit()
        if result.person_embeddings_created:
            svc.rebuild_index()
        return FaceBackfillResponse(**result.__dict__)
    except RuntimeError as e:
        svc.db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from e
    except (ImportError, ModuleNotFoundError, FileNotFoundError) as e:
        svc.db.rollback()
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "face01 runtime unavailable"
        ) from e


@router.patch("/faces/links/{link_id}", response_model=PhotoPersonOut)
def confirm_face(
    link_id: int, req: ConfirmFaceRequest, svc: FaceService = Depends(_face_service)
):
    link = _get_link_scoped(svc, link_id)
    _get_person_scoped(svc, req.person_id)
    try:
        return svc.confirm_face(link, req.person_id)
    except ValueError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from e


@router.delete("/faces/links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_face_link(link_id: int, svc: FaceService = Depends(_face_service)) -> Response:
    link = _get_link_scoped(svc, link_id)
    svc.delete_link(link)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/persons/{person_id}/faces", response_model=list[CandidateOut])
async def register_person_face(
    person_id: int,
    file: UploadFile = File(...),
    svc: FaceService = Depends(_face_service),
):
    _get_person_scoped(svc, person_id)
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

    photo = PhotoService(svc.db, svc.env_id).store_image(
        content=content,
        filename=file.filename or "reference.jpg",
        memo=f"参照顔登録 (person #{person_id})",
    )
    svc.register_reference(person_id, faces[0], photo.id)
    svc.db.commit()
    return []
