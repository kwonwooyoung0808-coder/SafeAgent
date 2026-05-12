from __future__ import annotations

from typing import Any, Literal, TypedDict

from pydantic import BaseModel, Field


class ViolationDetail(BaseModel):
    type: str
    description: str
    severity: Literal["HIGH", "MEDIUM", "LOW"]


class ResponseValidateRequest(BaseModel):
    agent_id: str
    query: str
    response: str
    # 생략 시 agent 의 등록된 기본 policy_id 사용. 둘 다 없으면 422.
    policy_id: str | None = None
    audit_query_id: str | None = None


class ResponseValidateResponse(BaseModel):
    status: Literal["APPROVED", "FLAGGED", "REJECTED"]
    compliance_score: float = 1.0
    violations: list[ViolationDetail] = Field(default_factory=list)
    audit_id: str
    trace_id: str


class ComplianceState(TypedDict, total=False):
    """LangGraph 상태 — Feature 2 워크플로우 노드 간 전달."""

    agent_id: str
    query: str
    response: str
    policy_id: str           # 단일 정책 (하위 호환)
    policy_ids: list[str]    # 다중 정책 (Stage A: 시스템 + 부서별 결합)
    audit_query_id: str | None
    trace_id: str            # PRD §6 추적 체인

    policy: dict[str, Any]
    policy_version: str | None  # Phase 3-A 활성 버전 (audit 기록용)
    rule_violations: list[dict[str, Any]]
    rule_rejected: bool

    llm_compliance_score: float
    llm_violations: list[dict[str, Any]]
    all_violations: list[dict[str, Any]]

    final_status: Literal["APPROVED", "FLAGGED", "REJECTED"]
    final_score: float

    audit_id: str
    error_message: str
