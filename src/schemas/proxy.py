from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from src.schemas.compliance import ViolationDetail


class ProxyChatRequest(BaseModel):
    """
    POST /v1/proxy/chat — Feature 1 → Sovereign AI → Feature 2 자동 연결.

    PRD 외 편의 엔드포인트. PRD 호환을 위해 Feature 1/2 개별 API는 그대로 유지됨.
    policy_id 생략 시 agent 의 등록된 기본 policy_id 사용 (둘 다 없으면 422).
    """

    agent_id: str = Field(min_length=1, max_length=80)
    policy_id: str | None = None
    query: str = Field(min_length=1, max_length=10_000)
    context: str | None = Field(default=None, max_length=20_000)


class ProxyChatResponse(BaseModel):
    status: Literal[
        "APPROVED",                # 정상 응답 통과
        "BLOCKED_BY_QUERY",        # Feature 1에서 질의 차단
        "FLAGGED",                 # Feature 2가 FLAGGED 판정 (응답은 반환됨)
        "REJECTED_BY_RESPONSE",    # Feature 2에서 응답 거부
        "FAILED",                  # 내부 오류
    ]
    final_response: str | None = Field(
        default=None,
        description="최종 사용자에게 전달할 응답. BLOCKED/REJECTED 시 None 또는 fallback 메시지.",
    )
    safe_response: str | None = Field(
        default=None,
        description=(
            "PRD §8 Safe Response Generator 가 생성한 안전 대체 응답. "
            "BLOCKED_BY_QUERY / REJECTED_BY_RESPONSE 일 때 채워진다."
        ),
    )
    query_audit_id: str | None = None
    response_audit_id: str | None = None
    risk_score: float | None = None
    compliance_score: float | None = None
    violations: list[ViolationDetail] = Field(default_factory=list)
    risk_reasons: list[str] = Field(default_factory=list)
    error_message: str | None = None
    trace_id: str
