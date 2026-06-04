"""人物エンドポイント。"""
from __future__ import annotations

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.schemas.event import EventOut
from app.schemas.person import (
    FaceImportStatus,
    PersonCreate,
    PersonImportResult,
    PersonOut,
    PersonUpdate,
)
from app.schemas.review import DismissRequest, MergeSuggestionOut
from app.services.face_import_service import FaceImportService, drain_all
from app.services.merge_service import PersonMergeService
from app.services.person_service import PersonService

router = APIRouter()


def _service(db: Session = Depends(get_db)) -> PersonService:
    return PersonService(db)


@router.get("", response_model=list[PersonOut])
def list_persons(
    q: str | None = Query(default=None, description="名前部分一致"),
    limit: int = 100,
    offset: int = 0,
    svc: PersonService = Depends(_service),
) -> list:
    return svc.list(q=q, limit=limit, offset=offset)


@router.post("", response_model=PersonOut, status_code=status.HTTP_201_CREATED)
def create_person(data: PersonCreate, svc: PersonService = Depends(_service)):
    return svc.create(data)


@router.post("/import", response_model=PersonImportResult)
async def import_persons(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    source: str = Form(default="friends_csv"),
    svc: PersonService = Depends(_service),
):
    content = await file.read()
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "CSV must be UTF-8") from e
    try:
        result = svc.import_friend_csv(text, source=source.strip() or "friends_csv")
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    # img_url 由来の参照顔取込をバックグラウンドで処理
    if result.face_queued > 0:
        background_tasks.add_task(drain_all)
    return result


@router.get("/import/face-status", response_model=FaceImportStatus)
def face_import_status(db: Session = Depends(get_db)):
    return FaceImportStatus(**FaceImportService(db).status())


@router.post("/import/process-faces", response_model=FaceImportStatus)
def process_faces(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """保留中の参照顔取込をバックグラウンドで再開。"""
    background_tasks.add_task(drain_all)
    return FaceImportStatus(**FaceImportService(db).status())


@router.post("/import/retry-faces", response_model=FaceImportStatus)
def retry_faces(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """failed を pending に戻して再処理。"""
    FaceImportService(db).retry_failed()
    background_tasks.add_task(drain_all)
    return FaceImportStatus(**FaceImportService(db).status())


class CountOut(BaseModel):
    count: int


@router.get("/count", response_model=CountOut)
def count_persons(
    q: str | None = Query(default=None), svc: PersonService = Depends(_service)
):
    return CountOut(count=svc.count(q=q))


@router.get("/merge-suggestions", response_model=list[MergeSuggestionOut])
def merge_suggestions(limit: int | None = None, db: Session = Depends(get_db)):
    """ベクトル近接の別人物ペア（重複の疑い）を提案。limit 未指定で全件。"""
    from app.face.registry import get_index
    from app.services.merge_suggest_service import MergeSuggestService

    return MergeSuggestService(db, get_index()).suggestions(limit=limit)


@router.post("/merge-suggestions/dismiss", status_code=status.HTTP_204_NO_CONTENT)
def dismiss_merge_suggestion(req: DismissRequest, db: Session = Depends(get_db)) -> Response:
    """「別人」として却下 → 再提案しない。"""
    from app.face.registry import get_index
    from app.services.merge_suggest_service import MergeSuggestService

    MergeSuggestService(db, get_index()).dismiss(req.person_a_id, req.person_b_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{person_id}", response_model=PersonOut)
def get_person(person_id: int, svc: PersonService = Depends(_service)):
    person = svc.get(person_id)
    if person is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "person not found")
    return person


@router.get("/{person_id}/events", response_model=list[EventOut])
def list_person_events(person_id: int, svc: PersonService = Depends(_service)):
    person = svc.get(person_id)
    if person is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "person not found")
    return person.events


@router.post("/{person_id}/events/{event_id}", response_model=EventOut)
def add_person_event(
    person_id: int,
    event_id: int,
    svc: PersonService = Depends(_service),
):
    person = svc.get(person_id)
    if person is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "person not found")
    event = svc.get_event(event_id)
    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "event not found")
    return svc.add_event(person, event)


@router.delete("/{person_id}/events/{event_id}")
def remove_person_event(
    person_id: int,
    event_id: int,
    svc: PersonService = Depends(_service),
) -> Response:
    person = svc.get(person_id)
    if person is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "person not found")
    event = svc.get_event(event_id)
    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "event not found")
    svc.remove_event(person, event)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/{person_id}", response_model=PersonOut)
def update_person(person_id: int, data: PersonUpdate, svc: PersonService = Depends(_service)):
    person = svc.get(person_id)
    if person is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "person not found")
    return svc.update(person, data)


class MergeRequest(BaseModel):
    source_id: int  # 吸収される側（統合後に削除）


@router.post("/{person_id}/merge", response_model=PersonOut)
def merge_person(person_id: int, req: MergeRequest, db: Session = Depends(get_db)):
    """source_id の人物を person_id（target）へ統合。

    誤検出/自動登録の重複を本人に吸収。ベクトルも移管され照合精度が向上。
    """
    try:
        return PersonMergeService(db).merge(source_id=req.source_id, target_id=person_id)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e


@router.delete("/{person_id}")
def delete_person(person_id: int, svc: PersonService = Depends(_service)) -> Response:
    person = svc.get(person_id)
    if person is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "person not found")
    svc.delete(person)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
