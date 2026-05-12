from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.core.dependencies import get_db
from src.database.models import InquiryModel

router = APIRouter(prefix="/v1/inquiry", tags=["inquiry"])


class InquiryCreate(BaseModel):
    agent_id: str | None = None
    user_id: str | None = None
    inquiry_type: str = Field(pattern="^(BLOCK_APPEAL|POLICY_QUESTION|OTHER)$")
    audit_id: str | None = None
    content: str = Field(min_length=1, max_length=2000)


class InquiryResolve(BaseModel):
    admin_reply: str = Field(min_length=1, max_length=2000)


class InquiryResponse(BaseModel):
    id: str
    agent_id: str | None
    user_id: str | None
    inquiry_type: str
    audit_id: str | None
    content: str
    status: str
    admin_reply: str | None
    created_at: datetime
    resolved_at: datetime | None


@router.post("", response_model=InquiryResponse, status_code=201)
def create_inquiry(payload: InquiryCreate, db: Session = Depends(get_db)) -> InquiryResponse:
    """사원이 문의를 제출한다."""
    row = InquiryModel(
        id=str(uuid.uuid4()),
        agent_id=payload.agent_id,
        user_id=payload.user_id,
        inquiry_type=payload.inquiry_type,
        audit_id=payload.audit_id,
        content=payload.content,
        status="PENDING",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _to_response(row)


@router.get("", response_model=list[InquiryResponse])
def list_inquiries(
    status: str | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
) -> list[InquiryResponse]:
    """관리자용: 전체 문의 목록 조회."""
    q = db.query(InquiryModel)
    if status:
        q = q.filter(InquiryModel.status == status)
    rows = q.order_by(InquiryModel.created_at.desc()).limit(limit).all()
    return [_to_response(r) for r in rows]


@router.get("/my", response_model=list[InquiryResponse])
def list_my_inquiries(
    user_id: str,
    limit: int = 20,
    db: Session = Depends(get_db),
) -> list[InquiryResponse]:
    """사원용: 내 문의 목록 조회."""
    rows = (
        db.query(InquiryModel)
        .filter(InquiryModel.user_id == user_id)
        .order_by(InquiryModel.created_at.desc())
        .limit(limit)
        .all()
    )
    return [_to_response(r) for r in rows]


@router.put("/{inquiry_id}/resolve", response_model=InquiryResponse)
def resolve_inquiry(
    inquiry_id: str,
    payload: InquiryResolve,
    db: Session = Depends(get_db),
) -> InquiryResponse:
    """관리자용: 문의 처리 완료 + 답변."""
    row = db.query(InquiryModel).filter(InquiryModel.id == inquiry_id).first()
    if not row:
        raise HTTPException(status_code=404, detail=f"inquiry_id={inquiry_id} 없음")
    if row.status == "RESOLVED":
        raise HTTPException(status_code=409, detail="이미 처리된 문의입니다.")

    row.status = "RESOLVED"
    row.admin_reply = payload.admin_reply
    row.resolved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return _to_response(row)


def _to_response(row: InquiryModel) -> InquiryResponse:
    return InquiryResponse(
        id=row.id,
        agent_id=row.agent_id,
        user_id=row.user_id,
        inquiry_type=row.inquiry_type,
        audit_id=row.audit_id,
        content=row.content,
        status=row.status,
        admin_reply=row.admin_reply,
        created_at=row.created_at,
        resolved_at=row.resolved_at,
    )
