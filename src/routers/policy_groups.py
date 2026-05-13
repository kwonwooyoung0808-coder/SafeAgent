"""Policy Group CRUD + 멤버 관리 API (PRD §X)."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.core.dependencies import get_db
from src.database.models import (
    AgentModel,
    AgentPolicyGroupMappingModel,
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


class PolicySummary(BaseModel):
    id: str
    name: str
    version: str
    is_active: bool


class AgentSummary(BaseModel):
    id: str
    name: str
    status: str


class PolicyGroupSummaryItem(BaseModel):
    id: str
    name: str
    description: str | None
    policies: list[PolicySummary] = Field(default_factory=list)
    agents: list[AgentSummary] = Field(default_factory=list)


class PolicyGroupSummaryResponse(BaseModel):
    groups: list[PolicyGroupSummaryItem]
    ungrouped_policies: list[PolicySummary] = Field(default_factory=list)
    total_groups: int
    total_ungrouped_policies: int


class PolicyGroupsForPolicyResponse(BaseModel):
    policy_id: str
    groups: list[PolicyGroupItem]
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


def _to_policy_summary(row: PolicyModel) -> PolicySummary:
    return PolicySummary(
        id=row.id,
        name=row.name,
        version=row.version,
        is_active=row.is_active,
    )


def _to_agent_summary(row: AgentModel) -> AgentSummary:
    return AgentSummary(id=row.id, name=row.name, status=row.status)


def _ensure_group(db: Session, group_id: str) -> PolicyGroupModel:
    row = db.query(PolicyGroupModel).filter(PolicyGroupModel.id == group_id).first()
    if not row:
        raise HTTPException(status_code=404, detail=f"group_id={group_id} 없음")
    return row


def _ensure_active_policy(db: Session, policy_id: str) -> PolicyModel:
    row = db.query(PolicyModel).filter(
        PolicyModel.id == policy_id,
        PolicyModel.is_active == True,
    ).first()
    if not row:
        raise HTTPException(
            status_code=422,
            detail=f"활성 정책이 아니거나 존재하지 않음: {policy_id}",
        )
    return row


# ──────────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────────


@router.get(
    "/summary",
    response_model=PolicyGroupSummaryResponse,
    summary="모든 그룹 + 그룹별 정책/agent + 미그룹 정책 한 번에 조회 (운영자 대시보드)",
)
def summarize_groups(db: Session = Depends(get_db)) -> PolicyGroupSummaryResponse:
    groups = db.query(PolicyGroupModel).order_by(PolicyGroupModel.created_at.desc()).all()
    summary_items: list[PolicyGroupSummaryItem] = []
    grouped_policy_ids: set[str] = set()

    for group in groups:
        policies = (
            db.query(PolicyModel)
            .join(PolicyGroupMemberModel, PolicyGroupMemberModel.policy_id == PolicyModel.id)
            .filter(PolicyGroupMemberModel.group_id == group.id)
            .order_by(PolicyModel.id.asc())
            .all()
        )
        agents = (
            db.query(AgentModel)
            .join(AgentPolicyGroupMappingModel, AgentPolicyGroupMappingModel.agent_id == AgentModel.id)
            .filter(AgentPolicyGroupMappingModel.group_id == group.id)
            .order_by(AgentModel.id.asc())
            .all()
        )
        grouped_policy_ids.update(policy.id for policy in policies)
        summary_items.append(PolicyGroupSummaryItem(
            id=group.id,
            name=group.name,
            description=group.description,
            policies=[_to_policy_summary(policy) for policy in policies],
            agents=[_to_agent_summary(agent) for agent in agents],
        ))

    ungrouped_query = db.query(PolicyModel)
    if grouped_policy_ids:
        ungrouped_query = ungrouped_query.filter(~PolicyModel.id.in_(grouped_policy_ids))
    ungrouped = ungrouped_query.order_by(PolicyModel.id.asc()).all()
    return PolicyGroupSummaryResponse(
        groups=summary_items,
        ungrouped_policies=[_to_policy_summary(policy) for policy in ungrouped],
        total_groups=len(summary_items),
        total_ungrouped_policies=len(ungrouped),
    )


@router.get(
    "",
    response_model=PolicyGroupListResponse,
    summary="정책 그룹 목록 조회",
)
def list_groups(db: Session = Depends(get_db)) -> PolicyGroupListResponse:
    rows = db.query(PolicyGroupModel).order_by(PolicyGroupModel.created_at.desc()).all()
    return PolicyGroupListResponse(
        items=[_to_item(db, r) for r in rows],
        total=len(rows),
    )


@router.get(
    "/{group_id}",
    response_model=PolicyGroupItem,
    summary="정책 그룹 단건 조회",
)
def get_group(group_id: str, db: Session = Depends(get_db)) -> PolicyGroupItem:
    row = db.query(PolicyGroupModel).filter(PolicyGroupModel.id == group_id).first()
    if not row:
        raise HTTPException(status_code=404, detail=f"group_id={group_id} 없음")
    return _to_item(db, row)


@router.get(
    "/policies/{policy_id}/groups",
    response_model=PolicyGroupsForPolicyResponse,
    summary="특정 정책이 속한 그룹 목록 조회 (역방향 조회)",
)
def list_groups_for_policy(
    policy_id: str,
    db: Session = Depends(get_db),
) -> PolicyGroupsForPolicyResponse:
    if not db.query(PolicyModel).filter(PolicyModel.id == policy_id).first():
        raise HTTPException(status_code=404, detail=f"policy_id={policy_id} 없음")
    rows = (
        db.query(PolicyGroupModel)
        .join(PolicyGroupMemberModel, PolicyGroupMemberModel.group_id == PolicyGroupModel.id)
        .filter(PolicyGroupMemberModel.policy_id == policy_id)
        .order_by(PolicyGroupModel.id.asc())
        .all()
    )
    return PolicyGroupsForPolicyResponse(
        policy_id=policy_id,
        groups=[_to_item(db, row) for row in rows],
        total=len(rows),
    )


@router.post(
    "",
    response_model=PolicyGroupItem,
    status_code=201,
    summary="정책 그룹 생성 (선택적으로 초기 멤버 정책 포함)",
)
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
    db.flush()
    for pid in payload.policy_ids:
        db.add(PolicyGroupMemberModel(group_id=group_id, policy_id=pid))
    db.commit()
    db.refresh(group)
    return _to_item(db, group)


@router.put(
    "/{group_id}/members",
    response_model=PolicyGroupItem,
    summary="[전체 교체] 멤버 정책 일괄 교체 — 기존 멤버 모두 삭제 후 payload로 대체",
)
def update_members(
    group_id: str,
    payload: PolicyGroupMembersUpdate,
    db: Session = Depends(get_db),
) -> PolicyGroupItem:
    """멤버 정책 일괄 교체 (set semantics). 기존 멤버는 모두 제거됨."""
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


@router.post(
    "/{group_id}/policies/{policy_id}",
    response_model=PolicyGroupItem,
    status_code=201,
    summary="[1건 추가] 정책 1개를 그룹에 추가 — 이미 연결된 경우 409",
)
def add_policy_to_group(
    group_id: str,
    policy_id: str,
    db: Session = Depends(get_db),
) -> PolicyGroupItem:
    row = _ensure_group(db, group_id)
    _ensure_active_policy(db, policy_id)
    existing = db.query(PolicyGroupMemberModel).filter(
        PolicyGroupMemberModel.group_id == group_id,
        PolicyGroupMemberModel.policy_id == policy_id,
    ).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"group_id={group_id} 에 policy_id={policy_id} 가 이미 연결되어 있음",
        )
    db.add(PolicyGroupMemberModel(group_id=group_id, policy_id=policy_id))
    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return _to_item(db, row)


@router.delete(
    "/{group_id}/policies/{policy_id}",
    response_model=PolicyGroupItem,
    summary="[1건 제거] 정책 1개를 그룹에서 제거",
)
def remove_policy_from_group(
    group_id: str,
    policy_id: str,
    db: Session = Depends(get_db),
) -> PolicyGroupItem:
    row = _ensure_group(db, group_id)
    member = db.query(PolicyGroupMemberModel).filter(
        PolicyGroupMemberModel.group_id == group_id,
        PolicyGroupMemberModel.policy_id == policy_id,
    ).first()
    if not member:
        raise HTTPException(
            status_code=404,
            detail=f"정책 그룹 멤버 없음 (group_id={group_id}, policy_id={policy_id})",
        )
    db.delete(member)
    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return _to_item(db, row)


@router.delete(
    "/{group_id}",
    status_code=204,
    response_class=Response,
    summary="[파괴적] 정책 그룹 삭제 — 멤버/agent 매핑은 FK CASCADE로 자동 정리",
)
def delete_group(group_id: str, db: Session = Depends(get_db)) -> Response:
    row = db.query(PolicyGroupModel).filter(PolicyGroupModel.id == group_id).first()
    if not row:
        raise HTTPException(status_code=404, detail=f"group_id={group_id} 없음")
    db.delete(row)
    db.commit()
    return Response(status_code=204)
