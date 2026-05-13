from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.core.dependencies import get_db, get_trace_id
from src.core.guards import get_active_agent_or_422, validate_combined_policies_active
from src.schemas.compliance import ViolationDetail
from src.core.config import get_settings
from src.schemas.proxy import ProxyChatRequest, ProxyChatResponse
from src.services.safe_response_generator import generate_safe_response
from src.services.sovereign_ai_client import SovereignAIClient
from src.services.violation_reporter import report_violation
from src.utils.agent_policies import resolve_agent_policy_ids
from src.workflows.input_guard_workflow import build_input_guard_graph
from src.workflows.response_guard_workflow import build_response_guard_graph

router = APIRouter(prefix="/v1/proxy", tags=["proxy"])


# ──────────────────────────────────────────────────────────────
# Sovereign AI 호출 — SOVEREIGN_AI_* 환경변수로 분리 (운영 시 회사 LLM URL 로 교체)
# Agent 별 LLM 매핑은 향후 AgentModel 컬럼으로 확장 예정
# ──────────────────────────────────────────────────────────────
async def _call_sovereign_ai(query: str, context: str | None = None) -> str:
    """SOVEREIGN_AI_URL 환경변수에 설정된 회사 자체 AI 호출."""
    client = SovereignAIClient()
    return await client.generate(query, context)


# ──────────────────────────────────────────────────────────────
# POST /v1/proxy/chat — Feature 1 → Sovereign AI → Feature 2 자동 연결
# ──────────────────────────────────────────────────────────────
@router.post("/chat", response_model=ProxyChatResponse)
async def proxy_chat(
    request: ProxyChatRequest,
    db: Session = Depends(get_db),
    trace_id: str = Depends(get_trace_id),
) -> ProxyChatResponse:
    """
    PRD 외 편의 엔드포인트. 다음 3단계를 자동으로 묶음:

    ① Feature 1 (질의 위험 감지) — input_guard_workflow 실행
    ② BLOCKED 아니면 Sovereign AI 호출 (현재 데모용 Ollama)
    ③ Feature 2 (응답 내규 검증) — response_guard_workflow 실행 (audit_query_id 자동 연결)

    호출자는 한 번의 API 호출로 전 과정 결과를 받을 수 있음.
    개별 단계 추적이 필요하면 query_audit_id / response_audit_id로 감사 로그 조회.
    """
    # ── 사전 검증 (FK 무결성) ──────────────────────────────────
    settings = get_settings()

    agent = get_active_agent_or_422(db, request.agent_id)

    # Stage A 정책 분리 전략 + Phase 2-C 그룹 결합
    # F1: 시스템 입력 정책만 사용 (보편 안전 필터)
    # F2: 시스템 + agent.policy_id + agent 가 속한 모든 그룹의 멤버 정책
    system_policy_id = settings.system_input_policy_id
    f2_policy_ids = resolve_agent_policy_ids(
        db,
        agent=agent,
        system_policy_id=system_policy_id,
        request_policy_id=request.policy_id,
    )

    # 모든 결합 정책이 활성 상태여야 함
    validate_combined_policies_active(db, f2_policy_ids)

    # ── ① Feature 1: 질의 위험 감지 (시스템 정책 고정) ────────
    query_graph = build_input_guard_graph()
    q_final: dict = await query_graph.ainvoke({
        "agent_id":  request.agent_id,
        "query":     request.query,
        "context":   request.context,
        "policy_id": system_policy_id,
        "trace_id":  trace_id,
    })

    query_audit_id = q_final.get("audit_id", "")
    risk_score = q_final.get("final_score", 0.0)
    risk_reasons = q_final.get("combined_reasons", [])

    if q_final.get("final_status") == "BLOCKED":
        safe_msg = generate_safe_response(
            stage="BLOCKED_BY_QUERY",
            violations=q_final.get("rule_violations") or [],
            risk_reasons=risk_reasons,
        )
        report_violation(
            stage="F1_QUERY",
            trace_id=trace_id,
            agent_id=request.agent_id,
            query_audit_id=query_audit_id,
            policy_version=q_final.get("policy_version"),
            original_query=request.query,
            violations=q_final.get("rule_violations") or [],
            risk_reasons=risk_reasons,
        )
        return ProxyChatResponse(
            status="BLOCKED_BY_QUERY",
            final_response=safe_msg,
            safe_response=safe_msg,
            query_audit_id=query_audit_id,
            risk_score=risk_score,
            risk_reasons=risk_reasons,
            trace_id=trace_id,
        )

    # ── ② Sovereign AI 호출 ────────────────────────────────────
    try:
        ai_response = await _call_sovereign_ai(request.query, request.context)
    except Exception as e:
        # str(e) 가 비어있는 예외 (ReadTimeout 등) 도 type 으로 진단
        detail = f"{type(e).__name__}: {e}" if str(e) else type(e).__name__
        return ProxyChatResponse(
            status="FAILED",
            query_audit_id=query_audit_id,
            risk_score=risk_score,
            error_message=f"Sovereign AI 호출 실패: {detail}",
            trace_id=trace_id,
        )

    # ── ③ Feature 2: 응답 내규 검증 (audit_query_id 자동 연결) ──
    # ── ③ Feature 2: 응답 검증 (시스템 + 부서 정책 결합) ───────
    compliance_graph = build_response_guard_graph()
    r_final: dict = await compliance_graph.ainvoke({
        "agent_id":       request.agent_id,
        "query":          request.query,
        "response":       ai_response,
        "policy_ids":     f2_policy_ids,  # Stage A: 시스템 + 부서 결합
        "audit_query_id": query_audit_id,
        "trace_id":       trace_id,
    })

    response_audit_id = r_final.get("audit_id", "")
    compliance_score = r_final.get("final_score", 1.0)
    raw_violations = r_final.get("all_violations", [])

    violations: list[ViolationDetail] = []
    for v in raw_violations:
        try:
            violations.append(ViolationDetail(**v))
        except Exception:
            pass

    final_status = r_final.get("final_status", "APPROVED")
    if final_status == "REJECTED":
        safe_msg = generate_safe_response(
            stage="REJECTED_BY_RESPONSE",
            violations=raw_violations,
            risk_reasons=risk_reasons,
        )
        report_violation(
            stage="F2_RESPONSE",
            trace_id=trace_id,
            agent_id=request.agent_id,
            query_audit_id=query_audit_id,
            response_audit_id=response_audit_id,
            policy_version=r_final.get("policy_version"),
            original_query=request.query,
            original_response=ai_response,
            violations=raw_violations,
            risk_reasons=risk_reasons,
        )
        return ProxyChatResponse(
            status="REJECTED_BY_RESPONSE",
            final_response=safe_msg,
            safe_response=safe_msg,
            query_audit_id=query_audit_id,
            response_audit_id=response_audit_id,
            risk_score=risk_score,
            compliance_score=compliance_score,
            violations=violations,
            risk_reasons=risk_reasons,
            trace_id=trace_id,
        )

    if final_status == "FLAGGED":
        return ProxyChatResponse(
            status="FLAGGED",
            final_response=ai_response,
            query_audit_id=query_audit_id,
            response_audit_id=response_audit_id,
            risk_score=risk_score,
            compliance_score=compliance_score,
            violations=violations,
            risk_reasons=risk_reasons,
            trace_id=trace_id,
        )

    return ProxyChatResponse(
        status="APPROVED",
        final_response=ai_response,
        query_audit_id=query_audit_id,
        response_audit_id=response_audit_id,
        risk_score=risk_score,
        compliance_score=compliance_score,
        violations=violations,
        risk_reasons=risk_reasons,
        trace_id=trace_id,
    )
