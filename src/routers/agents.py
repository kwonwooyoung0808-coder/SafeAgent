from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from src.core.dependencies import get_db
from pydantic import BaseModel

from src.database.models import (
    AgentModel,
    AgentPolicyGroupMappingModel,
    PolicyGroupModel,
    PolicyModel,
    QueryAuditLogModel,
    ResponseAuditLogModel,
)
from src.schemas.agent import AgentCreate, AgentPolicyUpdate, AgentResponse

router = APIRouter(prefix="/api/agents", tags=["agents"])


# ──────────────────────────────────────────────────────────────
# PRD 9: POST /api/agents — 에이전트 등록
# ──────────────────────────────────────────────────────────────
@router.post("", response_model=AgentResponse, status_code=201)
def create_agent(payload: AgentCreate, db: Session = Depends(get_db)) -> AgentResponse:
    """
    Sovereign AI 에이전트를 거버넌스 시스템에 등록.
    policy_id 지정 시 즉시 활성 정책 존재 여부 검증.
    중복 ID 등록 시 409 반환.
    """
    agent_id = payload.id or f"agent-{uuid.uuid4().hex[:8]}"

    if db.query(AgentModel).filter(AgentModel.id == agent_id).first():
        raise HTTPException(status_code=409, detail=f"agent_id={agent_id} 이미 존재")

    if payload.policy_id:
        policy = db.query(PolicyModel).filter(
            PolicyModel.id == payload.policy_id,
            PolicyModel.is_active == True,
        ).first()
        if not policy:
            raise HTTPException(
                status_code=422,
                detail=f"policy_id={payload.policy_id} 없음 또는 미활성",
            )

    now = datetime.now(timezone.utc)
    agent = AgentModel(
        id=agent_id,
        name=payload.name,
        description=payload.description,
        policy_id=payload.policy_id,
        status=payload.status,
        created_at=now,
        updated_at=now,
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)

    return AgentResponse(
        id=agent.id,
        name=agent.name,
        description=agent.description,
        policy_id=agent.policy_id,
        status=agent.status,
        created_at=agent.created_at,
        updated_at=agent.updated_at,
    )


# ──────────────────────────────────────────────────────────────
# GET /api/agents — 에이전트 목록 (운영자 조회용)
# ──────────────────────────────────────────────────────────────
@router.get("", response_model=list[AgentResponse])
def list_agents(
    status: str | None = None,
    db: Session = Depends(get_db),
) -> list[AgentResponse]:
    """등록된 에이전트 전체 목록.

    status 쿼리 파라미터로 ACTIVE / INACTIVE 등 필터링 가능 (생략 시 전체).
    """
    q = db.query(AgentModel)
    if status:
        q = q.filter(AgentModel.status == status)
    rows = q.order_by(AgentModel.created_at.desc()).all()
    return [
        AgentResponse(
            id=a.id,
            name=a.name,
            description=a.description,
            policy_id=a.policy_id,
            status=a.status,
            created_at=a.created_at,
            updated_at=a.updated_at,
        )
        for a in rows
    ]


# ──────────────────────────────────────────────────────────────
# PRD 9: GET /api/agents/{agent_id} — 에이전트 조회
# ──────────────────────────────────────────────────────────────
@router.get("/{agent_id}", response_model=AgentResponse)
def get_agent(agent_id: str, db: Session = Depends(get_db)) -> AgentResponse:
    agent = db.query(AgentModel).filter(AgentModel.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail=f"agent_id={agent_id} 없음")

    return AgentResponse(
        id=agent.id,
        name=agent.name,
        description=agent.description,
        policy_id=agent.policy_id,
        status=agent.status,
        created_at=agent.created_at,
        updated_at=agent.updated_at,
    )


# ──────────────────────────────────────────────────────────────
# PRD 9: PUT /api/agents/{agent_id}/policy — 정책 연결
# ──────────────────────────────────────────────────────────────
@router.put("/{agent_id}/policy", response_model=AgentResponse)
def update_agent_policy(
    agent_id: str,
    payload: AgentPolicyUpdate,
    db: Session = Depends(get_db),
) -> AgentResponse:
    """
    에이전트에 활성 정책을 연결.
    비활성 정책 연결 시도 시 422 반환.
    """
    agent = db.query(AgentModel).filter(AgentModel.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail=f"agent_id={agent_id} 없음")

    policy = db.query(PolicyModel).filter(
        PolicyModel.id == payload.policy_id,
        PolicyModel.is_active == True,
    ).first()
    if not policy:
        raise HTTPException(
            status_code=422,
            detail=f"policy_id={payload.policy_id} 없음 또는 미활성",
        )

    agent.policy_id = payload.policy_id
    agent.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(agent)

    return AgentResponse(
        id=agent.id,
        name=agent.name,
        description=agent.description,
        policy_id=agent.policy_id,
        status=agent.status,
        created_at=agent.created_at,
        updated_at=agent.updated_at,
    )


# ──────────────────────────────────────────────────────────────
# PRD 9: GET /api/agents/{agent_id}/audit — 감사 이력
# ──────────────────────────────────────────────────────────────
@router.get("/{agent_id}/audit")
def get_agent_audit(
    agent_id: str,
    limit: int = 50,
    db: Session = Depends(get_db),
) -> dict:
    """
    에이전트의 query / response 감사 이력 조회.
    최근순 정렬, 기본 50건 제한.
    """
    if not db.query(AgentModel).filter(AgentModel.id == agent_id).first():
        raise HTTPException(status_code=404, detail=f"agent_id={agent_id} 없음")

    queries = (
        db.query(QueryAuditLogModel)
        .filter(QueryAuditLogModel.agent_id == agent_id)
        .order_by(QueryAuditLogModel.created_at.desc())
        .limit(limit)
        .all()
    )
    responses = (
        db.query(ResponseAuditLogModel)
        .filter(ResponseAuditLogModel.agent_id == agent_id)
        .order_by(ResponseAuditLogModel.created_at.desc())
        .limit(limit)
        .all()
    )

    return {
        "agent_id": agent_id,
        "query_audits": [
            {
                "audit_id":     q.id,
                "query":        q.query,
                "status":       q.status,
                "risk_score":   q.risk_score,
                "action_taken": q.action_taken,
                "created_at":   q.created_at,
            }
            for q in queries
        ],
        "response_audits": [
            {
                "audit_id":         r.id,
                "query_audit_id":   r.query_audit_id,
                "status":           r.status,
                "compliance_score": r.compliance_score,
                "violation_count":  len(r.violations or []),
                "created_at":       r.created_at,
            }
            for r in responses
        ],
    }


# ──────────────────────────────────────────────────────────────
# Phase 2-C: Agent ↔ Policy Group 매핑
# ──────────────────────────────────────────────────────────────


class AgentGroupAssign(BaseModel):
    group_id: str


class AgentGroupListItem(BaseModel):
    group_id: str
    name: str
    policy_ids: list[str]


def _ensure_agent(db: Session, agent_id: str) -> AgentModel:
    agent = db.query(AgentModel).filter(AgentModel.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail=f"agent_id={agent_id} 없음")
    return agent


def _ensure_group(db: Session, group_id: str) -> PolicyGroupModel:
    group = db.query(PolicyGroupModel).filter(PolicyGroupModel.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail=f"group_id={group_id} 없음")
    return group


@router.post("/{agent_id}/policy-groups", status_code=201)
def assign_group(
    agent_id: str,
    payload: AgentGroupAssign,
    db: Session = Depends(get_db),
) -> dict:
    """에이전트에 정책 그룹 할당. 이미 매핑되어 있으면 409."""
    _ensure_agent(db, agent_id)
    _ensure_group(db, payload.group_id)

    existing = db.query(AgentPolicyGroupMappingModel).filter(
        AgentPolicyGroupMappingModel.agent_id == agent_id,
        AgentPolicyGroupMappingModel.group_id == payload.group_id,
    ).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"agent_id={agent_id} 는 이미 group_id={payload.group_id} 에 속해있음",
        )

    db.add(AgentPolicyGroupMappingModel(agent_id=agent_id, group_id=payload.group_id))
    db.commit()
    return {"agent_id": agent_id, "group_id": payload.group_id, "assigned": True}


@router.delete("/{agent_id}/policy-groups/{group_id}", status_code=204, response_class=Response)
def unassign_group(
    agent_id: str,
    group_id: str,
    db: Session = Depends(get_db),
) -> Response:
    row = db.query(AgentPolicyGroupMappingModel).filter(
        AgentPolicyGroupMappingModel.agent_id == agent_id,
        AgentPolicyGroupMappingModel.group_id == group_id,
    ).first()
    if not row:
        raise HTTPException(
            status_code=404,
            detail=f"매핑 없음 (agent_id={agent_id}, group_id={group_id})",
        )
    db.delete(row)
    db.commit()
    return Response(status_code=204)


@router.get("/{agent_id}/policy-groups", response_model=list[AgentGroupListItem])
def list_agent_groups(
    agent_id: str,
    db: Session = Depends(get_db),
) -> list[AgentGroupListItem]:
    _ensure_agent(db, agent_id)

    from src.database.models import PolicyGroupMemberModel

    rows = (
        db.query(PolicyGroupModel)
        .join(
            AgentPolicyGroupMappingModel,
            AgentPolicyGroupMappingModel.group_id == PolicyGroupModel.id,
        )
        .filter(AgentPolicyGroupMappingModel.agent_id == agent_id)
        .all()
    )

    result: list[AgentGroupListItem] = []
    for g in rows:
        member_pids = [
            m.policy_id
            for m in db.query(PolicyGroupMemberModel)
            .filter(PolicyGroupMemberModel.group_id == g.id)
            .all()
        ]
        result.append(AgentGroupListItem(group_id=g.id, name=g.name, policy_ids=member_pids))
    return result
