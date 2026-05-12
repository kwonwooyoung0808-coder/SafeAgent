from __future__ import annotations

from typing import Any, Literal, TypedDict

from pydantic import BaseModel, Field


class QueryCheckRequest(BaseModel):
    agent_id: str = Field(min_length=1)
    # query 길이 상한: 메모리 폭발/DB 부담 방지. 일반 사용자 질의에 충분한 10K자.
    query: str = Field(min_length=1, max_length=10_000)
    context: str | None = Field(default=None, max_length=20_000)
    # 생략 시 agent 의 등록된 기본 policy_id 사용. 둘 다 없으면 422.
    policy_id: str | None = Field(default=None, min_length=1)


class QueryCheckResponse(BaseModel):
    status: Literal["BLOCKED", "WARNED", "PASSED"]
    risk_score: float = 0.0
    risk_reasons: list[str] = Field(default_factory=list)
    action_taken: Literal["BLOCK", "LOG", "PASS"]
    audit_id: str
    trace_id: str


class QueryRiskState(TypedDict, total=False):
    """LangGraph 상태 — 노드 간 전달되는 부분 업데이트 dict."""

    agent_id: str
    query: str
    context: str | None
    policy_id: str
    trace_id: str

    policy: dict[str, Any]
    policy_version: str | None  # Phase 3-A 활성 버전 (audit 기록용)
    rule_violations: list[dict[str, Any]]
    rule_blocked: bool

    final_status: Literal["BLOCKED", "WARNED", "PASSED"]
    final_score: float
    action_taken: Literal["BLOCK", "LOG", "PASS"]
    combined_reasons: list[str]  # rule_violations 텍스트 (Phase 1: F1 LLM 미사용)

    audit_id: str
    error_message: str
