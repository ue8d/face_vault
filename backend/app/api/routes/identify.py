"""「この人誰だっけ？」エンドポイント。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_env_id
from app.db.base import get_db
from app.services.identify_service import IdentifyService
from app.services.person_service import PersonService

router = APIRouter()


class IdentifyRequest(BaseModel):
    person_id: int


class IdentifyResponse(BaseModel):
    person_id: int
    answer: str


@router.post("/identify-person", response_model=IdentifyResponse)
async def identify_person(
    req: IdentifyRequest,
    db: Session = Depends(get_db),
    env_id: int = Depends(get_env_id),
):
    """人物について、名前/関係性/メモ/初回・最終撮影/枚数/共起人物/
    関連イベント を文脈に回答。AI未設定時はテンプレ回答。"""
    person = PersonService(db, env_id).get(req.person_id)
    if person is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "person not found")
    answer = await IdentifyService(db).answer(person)
    return IdentifyResponse(person_id=person.id, answer=answer)
