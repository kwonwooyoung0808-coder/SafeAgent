"""Policy Group CRUD + 멤버 관리 API (PRD §X)."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.core.dependencies import get_db
from src.database.models import (
    PolicyGroupMemberModel,
    PolicyGroupModel,
    PolicyModel,
)

router = APIRouter(prefix="/v1/policy-groups", tags=["policy-groups"])


# ──────────────────────────────────────────────────────────────
# Schemas
# ──────────────────────────────────────────────────────────────


class PolicyGroupCreate(BaseModel):
    id: str | None = None  # 생략 시 UUID 자동 발급
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    policy_ids: list[str] = Field(default_factory=list)


class PolicyGroupItem(BaseModel):
    id: str
    name: str
    description: str | None
    policy_ids: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class PolicyGroupListResponse(BaseModel):
    items: list[PolicyGroupItem]
    total: int


class PolicyGroupMembersUpdate(BaseModel):
    policy_ids: list[str]


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────


def _validate_policies_exist(db: Session, policy_ids: list[str]) -> None:
    """주어진 정책 ID 들이 모두 활성 상태로 존재하는지 검증. 부재 시 422."""
    if not policy_ids:
        return
    found = {
        row.id
        for row in db.query(PolicyModel.id)
        .filter(PolicyModel.id.in_(policy_ids), PolicyModel.is_active == True)
        .all()
    }
    missing = [pid for pid in policy_ids if pid not in found]
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"활성 정책이 아니거나 존재하지 않음: {missing}",
        )


def _member_policy_ids(db: Session, group_id: str) -> list[str]:
    rows = (
        db.query(PolicyGroupMemberModel.policy_id)
        .filter(PolicyGroupMemberModel.group_id == group_id)
        .all()
    )
    return [r[0] for r in rows]


def _to_item(db: Session, row: PolicyGroupModel) -> PolicyGroupItem:
    return PolicyGroupItem(
        id=row.id,
        name=row.name,
        description=row.description,
        policy_ids=_member_policy_ids(db, row.id),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


# ──────────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────────


@router.post("", response_model=PolicyGroupItem, status_code=201)
def create_group(
    payload: PolicyGroupCreate,
    db: Session = Depends(get_db),
) -> PolicyGroupItem:
    group_id = payload.id or str(uuid4())

    if db.query(PolicyGroupModel).filter(PolicyGroupModel.id == group_id).first():
        raise HTTPException(status_code=409, detail=f"group_id={group_id} 이미 존재")

    _validate_policies_exist(db, payload.policy_ids)

    group = PolicyGroupModel(
        id=group_id,
        name=payload.name,
        description=payload.description,
    )
    db.add(group)
    db.flush()  # group INSERT 먼저 보장 (FK 충돌 방지)
    for pid in payload.policy_ids:
        db.add(PolicyGroupMemberModel(group_id=group_id, policy_id=pid))
    db.commit()
    db.refresh(group)
    return _to_item(db, group)


@router.get("", response_model=PolicyGroupListResponse)
def list_groups(db: Session = Depends(get_db)) -> PolicyGroupListResponse:
    rows = db.query(PolicyGroupModel).order_by(PolicyGroupModel.created_at.desc()).all()
    return PolicyGroupListResponse(
        items=[_to_item(db, r) for r in rows],
        total=len(rows),
    )


@router.get("/{group_id}", response_model=PolicyGroupItem)
def get_group(group_id: str, db: Session = Depends(get_db)) -> PolicyGroupItem:
    row = db.query(PolicyGroupModel).filter(PolicyGroupModel.id == group_id).first()
    if not row:
        raise HTTPException(status_code=404, detail=f"group_id={group_id} 없음")
    return _to_item(db, row)


@router.delete("/{group_id}", status_code=204, response_class=Response)
def delete_group(group_id: str, db: Session = Depends(get_db)) -> Response:
    row = db.query(PolicyGroupModel).filter(PolicyGroupModel.id == group_id).first()
    if not row:
        raise HTTPException(status_code=404, detail=f"group_id={group_id} 없음")
    # 멤버/매핑은 FK ondelete CASCADE 로 자동 정리
    db.delete(row)
    db.commit()
    return Response(status_code=204)


@router.put("/{group_id}/members", response_model=PolicyGroupItem)
def update_members(
    group_id: str,
    payload: PolicyGroupMembersUpdate,
    db: Session = Depends(get_db),
) -> PolicyGroupItem:
    """멤버 정책 일괄 교체 (set semantics)."""
    row = db.query(PolicyGroupModel).filter(PolicyGroupModel.id == group_id).first()
    if not row:
        raise HTTPException(status_code=404, detail=f"group_id={group_id} 없음")

    _validate_policies_exist(db, payload.policy_ids)

    db.query(PolicyGroupMemberModel).filter(
        PolicyGroupMemberModel.group_id == group_id
    ).delete()
    for pid in payload.policy_ids:
        db.add(PolicyGroupMemberModel(group_id=group_id, policy_id=pid))

    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return _to_item(db, row)
