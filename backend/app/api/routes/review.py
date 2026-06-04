"""確認キュー エンドポイント。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.face.registry import get_index
from app.schemas.review import ReviewCountOut, ReviewItemOut
from app.services.review_service import ReviewService

router = APIRouter()


@router.get("/review/faces", response_model=list[ReviewItemOut])
def review_faces(limit: int = 30, offset: int = 0, db: Session = Depends(get_db)):
    """割当が必要 / 低信頼の検出顔を候補付きで返す。"""
    return ReviewService(db, get_index()).faces(limit=limit, offset=offset)


@router.get("/review/count", response_model=ReviewCountOut)
def review_count(db: Session = Depends(get_db)):
    return ReviewCountOut(count=ReviewService(db, get_index()).count())
