from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.core.config import get_settings
from src.core.dependencies import get_db, get_trace_id
from src.core.guards import get_active_agent_or_422, validate_combined_policies_active
from src.database.models import QueryAuditLogModel
from src.schemas.compliance import (
    ResponseValidateRequest,
    ResponseValidateResponse,
    ViolationDetail,
)
from src.services.violation_reporter import report_violation
from src.utils.agent_policies import resolve_agent_policy_ids
from src.workflows.response_guard_workflow import build_response_guard_graph

router = APIRouter(prefix="/v1/response-guard", tags=["response-guard"])


@router.post("/validate", response_model=ResponseValidateResponse)
async def response_guard_validate(
    request: ResponseValidateRequest,
    db: Session = Depends(get_db),
    trace_id: str = Depends(get_trace_id),
) -> ResponseValidateResponse:
    """
    응답 내규 준수 검증 (Feature 2).

    [정책 결정 — Stage A 분리 전략]
    F2 는 시스템 입력 정책 + agent 의 부서별 정책을 결합한 가상 정책으로 평가.
    request.policy_id 가 명시되면 agent.policy_id 보다 우선.
    """
    settings = get_settings()

    agent = get_active_agent_or_422(db, request.agent_id)

    system_policy_id = settings.system_input_policy_id

    # Phase 2-C: 시스템 + agent.policy_id (legacy) + agent 가 속한 그룹의 모든 멤버 정책
    policy_ids = resolve_agent_policy_ids(
        db,
        agent=agent,
        system_policy_id=system_policy_id,
        request_policy_id=request.policy_id,
    )

    # FK 사전 검증 — 모든 정책이 활성 상태여야 함
    validate_combined_policies_active(db, policy_ids)

    # Feature 1 연결 ID 유효성 검증 (선택적)
    if request.audit_query_id:
        qal = db.query(QueryAuditLogModel).filter(
            QueryAuditLogModel.id == request.audit_query_id
        ).first()
        if not qal:
            raise HTTPException(
                status_code=422,
                detail=f"audit_query_id={request.audit_query_id} 없음",
            )
        # F2-4: 다른 에이전트의 query audit 을 본 에이전트의 response audit 에
        # 연결하는 것은 데이터 무결성 위반 → 422 거부
        if qal.agent_id != request.agent_id:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"audit_query_id={request.audit_query_id} 의 agent_id 불일치 "
                    f"(query audit agent={qal.agent_id}, request agent={request.agent_id})"
                ),
            )

    graph = build_response_guard_graph()
    final: dict = await graph.ainvoke({
        "agent_id":       request.agent_id,
        "query":          request.query,
        "response":       request.response,
        "policy_ids":     policy_ids,  # Stage A: 시스템 + 부서 결합
        "audit_query_id": request.audit_query_id,
        "trace_id":       trace_id,
    })

    raw_violations = final.get("all_violations", [])
    violations: list[ViolationDetail] = []
    for v in raw_violations:
        try:
            violations.append(ViolationDetail(**v))
        except Exception:
            pass

    if final.get("final_status") == "REJECTED":
        report_violation(
            stage="F2_RESPONSE",
            trace_id=trace_id,
            agent_id=request.agent_id,
            query_audit_id=request.audit_query_id,
            response_audit_id=final.get("audit_id"),
            policy_version=final.get("policy_version"),
            original_query=request.query,
            original_response=request.response,
            violations=raw_violations,
        )

    return ResponseValidateResponse(
        status=final.get("final_status", "APPROVED"),
        compliance_score=final.get("final_score", 1.0),
        violations=violations,
        audit_id=final.get("audit_id", ""),
        trace_id=trace_id,
    )
