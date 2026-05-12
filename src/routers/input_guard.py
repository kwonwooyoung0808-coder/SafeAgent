from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.core.config import get_settings
from src.core.dependencies import get_db, get_trace_id
from src.database.models import AgentModel, PolicyModel
from src.schemas.query_risk import QueryCheckRequest, QueryCheckResponse
from src.services.violation_reporter import report_violation
from src.workflows.input_guard_workflow import build_input_guard_graph

router = APIRouter(prefix="/v1/input-guard", tags=["input-guard"])


@router.post("/check", response_model=QueryCheckResponse)
async def input_guard_check(
    request: QueryCheckRequest,
    db: Session = Depends(get_db),
    trace_id: str = Depends(get_trace_id),
) -> QueryCheckResponse:
    """
    쿼리 위험성 평가 (Feature 1).

    [정책 결정 — Stage A 분리 전략]
    F1 은 모든 사용자에게 동일한 보편 안전 정책 (SYSTEM_INPUT_POLICY_ID) 만 적용.
    request/agent 의 policy_id 는 무시된다 (보안성, 일관성 보장).
    """
    settings = get_settings()

    agent = db.query(AgentModel).filter(
        AgentModel.id == request.agent_id,
        AgentModel.status == "ACTIVE",
    ).first()
    if not agent:
        raise HTTPException(
            status_code=422,
            detail=f"agent_id={request.agent_id} 없음 또는 비활성",
        )

    # F1 은 시스템 입력 정책만 사용
    system_policy_id = settings.system_input_policy_id
    policy = db.query(PolicyModel).filter(
        PolicyModel.id == system_policy_id,
        PolicyModel.is_active == True,
    ).first()
    if not policy:
        raise HTTPException(
            status_code=500,
            detail=(
                f"시스템 입력 정책 '{system_policy_id}' 미설정 또는 비활성. "
                f"관리자가 SYSTEM_INPUT_POLICY_ID 환경변수를 확인해야 합니다."
            ),
        )

    graph = build_input_guard_graph()
    final: dict = await graph.ainvoke({
        "agent_id":  request.agent_id,
        "query":     request.query,
        "context":   request.context,
        "policy_id": system_policy_id,
        "trace_id":  trace_id,
    })

    if final.get("final_status") == "BLOCKED":
        report_violation(
            stage="F1_QUERY",
            trace_id=trace_id,
            agent_id=request.agent_id,
            query_audit_id=final.get("audit_id"),
            policy_version=final.get("policy_version"),
            original_query=request.query,
            violations=final.get("rule_violations") or [],
            risk_reasons=final.get("combined_reasons", []),
        )

    return QueryCheckResponse(
        status=final.get("final_status", "PASSED"),
        risk_score=final.get("final_score", 0.0),
        # combined_reasons = 룰 위반 텍스트 (LLM 사유는 Phase 1 에서 제거됨)
        risk_reasons=final.get("combined_reasons", []),
        action_taken=final.get("action_taken", "PASS"),
        audit_id=final.get("audit_id", ""),
        trace_id=trace_id,
    )
