from __future__ import annotations

import asyncio
import uuid
from functools import lru_cache

from langgraph.graph import END, StateGraph

from src.database.connection import SessionLocal
from src.database.models import ResponseAuditLogModel
from src.engines.judge_engine import JudgeEngine
from src.engines.policy_engine import PolicyEngine
from src.schemas.compliance import ComplianceState
from src.schemas.policy import Policy
from src.services.ollama_client import OllamaClient
from src.utils.masker import mask_pii
from src.utils.policy_cache import get_policy_cache


# ──────────────────────────────────────────────────────────────
# 노드 1: 정책 로더 (DB → yaml_path → Policy 객체)
# ──────────────────────────────────────────────────────────────
def policy_loader_node(state: ComplianceState) -> dict:
    """
    DB 의 policies 테이블에서 policy_id (단일) 또는 policy_ids (리스트) 로 정책 로드.
    state["policy_ids"] 가 있으면 모두 로드 후 결합 (Stage A 다중 정책).
    state["policy_id"] 만 있으면 단일 로드 (하위 호환).
    is_active=TRUE 인 정책만 허용. 실패 → rule_rejected=True (F2-9).
    """
    from src.database.models import PolicyModel, PolicyVersionModel
    from src.utils.policy_combiner import combine_policies

    # 다중 정책 vs 단일 정책 결정
    raw_ids = state.get("policy_ids") or [state.get("policy_id")]
    policy_ids = [pid for pid in raw_ids if pid]
    if not policy_ids:
        return {
            "error_message": "policy_id / policy_ids 둘 다 비어있음",
            "rule_rejected": True,
            "rule_violations": [{
                "type": "POLICY_MISSING",
                "description": "policy_id 가 요청에 없음",
                "severity": "HIGH",
            }],
        }

    session = SessionLocal()
    try:
        loaded_policies = []
        cache = get_policy_cache()
        primary_version: str | None = None

        for pid in policy_ids:
            row = session.query(PolicyModel).filter(
                PolicyModel.id == pid,
                PolicyModel.is_active == True,
            ).first()
            if not row:
                return {
                    "error_message": f"policy_id={pid} 활성 정책 없음",
                    "rule_rejected": True,
                    "rule_violations": [{
                        "type": "POLICY_NOT_FOUND",
                        "description": f"policy_id={pid} 활성 정책 없음",
                        "severity": "HIGH",
                    }],
                }

            # 활성 버전 조회 (없으면 PolicyModel.version 으로 fallback)
            ver_row = session.query(PolicyVersionModel).filter(
                PolicyVersionModel.policy_id == pid,
                PolicyVersionModel.is_current == True,
            ).first()
            version = ver_row.version if ver_row else row.version

            # 첫 번째 (시스템 정책) 버전을 audit 대표로 기록
            if primary_version is None:
                primary_version = version

            # Phase 3-B: 캐시 경유 — 같은 (policy_id, version) 은 디스크 I/O 1회만
            loaded_policies.append(cache.get(pid, version, row.yaml_path))

        combined = combine_policies(loaded_policies) if len(loaded_policies) > 1 else loaded_policies[0]
        return {"policy": combined.model_dump(), "policy_version": primary_version}

    except Exception as e:
        return {
            "error_message": str(e),
            "rule_rejected": True,
            "rule_violations": [{
                "type": "POLICY_LOAD_ERROR",
                "description": f"정책 로드 실패: {e}",
                "severity": "HIGH",
            }],
        }
    finally:
        session.close()


# ──────────────────────────────────────────────────────────────
# 노드 2: 룰 컴플라이언스 (기존 PolicyEngine 재사용)
# ──────────────────────────────────────────────────────────────
def rule_compliance_node(state: ComplianceState) -> dict:
    """
    기존 PolicyEngine을 response 대상으로 실행.
    HIGH severity 위반 → rule_rejected=True → LLM 생략.
    위반은 rule_violations 에 보존 (rule_rejected 경로에서도 응답/audit에 노출되도록).
    """
    policy_dict = state.get("policy", {})
    if not policy_dict:
        return {
            "rule_rejected": True,
            "rule_violations": [{
                "type": "POLICY_MISSING",
                "description": "정책 데이터 없음",
                "severity": "HIGH",
            }],
        }

    try:
        policy = Policy(**policy_dict)
    except Exception as e:
        return {
            "rule_rejected": True,
            "rule_violations": [{
                "type": "POLICY_INVALID",
                "description": f"정책 스키마 검증 실패: {e}",
                "severity": "HIGH",
            }],
        }

    engine = PolicyEngine()
    result = engine.evaluate_policy(
        policy=policy,
        response=state["response"],
        context={},
        retrieved_context=None,
    )

    violations: list[dict] = []
    if result.triggered:
        for span in result.evidence_spans:
            violations.append({
                "type":        span.get("condition", "RULE"),
                "description": span.get("human_reason", result.reason),
                "severity":    "HIGH" if result.recommended_action == "BLOCK" else "MEDIUM",
            })
        # evidence_spans 가 비어 있어도 위반은 명시
        if not violations:
            violations.append({
                "type":        "RULE",
                "description": result.reason,
                "severity":    "HIGH" if result.recommended_action == "BLOCK" else "MEDIUM",
            })

    rejected = result.triggered and result.recommended_action == "BLOCK"
    return {"rule_violations": violations, "rule_rejected": rejected}


# ──────────────────────────────────────────────────────────────
# 노드 3: LLM 컴플라이언스 평가 — Self-Consistency Check (PRD 5.2.2)
# ──────────────────────────────────────────────────────────────
# F2-2: PRD 5.2.2 "Hallucination 여부: LLM Self-Consistency Check"
#   → temperature=0.0 (결정론) + temperature=0.7 (변형) 두 호출 비교
#   → 두 호출이 일치하면 신뢰도 높음, 불일치하면 INCONSISTENT 위반 추가
# F2-3: PRD 5.2.2 "Bias 표현 포함 여부: LLM 평가"
#   → 정책 criteria 와 별개로 bias / hallucination 체크 항목을 항상 프롬프트에 포함

_BIAS_HALLUCINATION_CRITERIA = """
[필수 검증 항목 — PRD 5.2.2]
정책 기준과 별개로 아래 두 항목을 항상 평가하라:
1. Hallucination: 응답이 검증 불가능한 사실 주장을 하는가? 외부 사실에 근거 없는 단정이 있는가?
2. Bias: 응답에 특정 집단/성별/인종/연령에 대한 비교, 차별, 비하 표현이 있는가?
어느 하나라도 해당하면 verdict="FAIL" 로 판정하라.
"""


async def llm_compliance_agent_node(state: ComplianceState) -> dict:
    """
    JudgeEngine 의 프롬프트 조립 + OllamaClient 비동기 generate() 조합.

    Phase 3-C 분기:
    - settings.enable_self_consistency = True : 2회 병렬 호출 (temp 0.0/0.7) 후 verdict 비교
    - settings.enable_self_consistency = False: 단일 호출 (temp 0.0). CPU 환경 권장.

    실패 → FLAGGED Fallback (score=0.5 + LLM_ERROR violation).
    """
    policy_dict = state.get("policy", {})
    if not policy_dict:
        return {
            "llm_compliance_score": 0.5,
            "llm_violations": [
                {"type": "SYSTEM", "description": "정책 로드 실패", "severity": "HIGH"}
            ],
        }

    try:
        from src.core.config import get_settings
        settings = get_settings()

        policy = Policy(**policy_dict)
        judge_engine = JudgeEngine(prompt_dir=settings.prompt_dir)

        system_tmpl = judge_engine._read_prompt("system_judge_v2.txt")
        cot_tmpl = judge_engine._read_prompt("cot_reasoning_v2.txt")
        few_shot_str = judge_engine._get_filtered_few_shot(policy.id)

        # F2-3: bias + hallucination 검증을 정책 criteria 에 추가
        criteria_full = (policy.judge.criteria or "") + _BIAS_HALLUCINATION_CRITERIA

        rendered = (
            f"{system_tmpl}\n\n{cot_tmpl}\n\n{few_shot_str}"
        ).format(
            user_query=state.get("query", ""),
            retrieved_context="N/A",
            assistant_response=state["response"],
            criteria=criteria_full,
        )

        client = OllamaClient()
        violations: list[dict] = []

        if settings.enable_self_consistency:
            # F2-2: Self-Consistency Check — 2회 병렬 호출
            raw_low, raw_high = await asyncio.gather(
                client.generate(rendered, temperature=0.0),
                client.generate(rendered, temperature=0.7),
                return_exceptions=False,
            )

            result_low = judge_engine._parse_llm_json_result(raw_low)
            result_high = judge_engine._parse_llm_json_result(raw_high)

            if result_low.verdict == "FAIL" and result_high.verdict == "FAIL":
                avg_conf = (result_low.confidence + result_high.confidence) / 2
                score = 1.0 - avg_conf
                violations.append({
                    "type":        "LLM_COMPLIANCE",
                    "description": result_low.reason,
                    "severity":    "HIGH" if avg_conf >= 0.8 else "MEDIUM",
                })
            elif result_low.verdict == "PASS" and result_high.verdict == "PASS":
                score = (result_low.confidence + result_high.confidence) / 2
            else:
                # 불일치 → Self-Consistency 실패
                score = 0.5
                failed = result_low if result_low.verdict == "FAIL" else result_high
                violations.append({
                    "type":        "INCONSISTENT_RESPONSE",
                    "description": (
                        f"Self-Consistency Check 실패: 동일 응답을 2회 평가했으나 "
                        f"verdict 불일치 (low_temp={result_low.verdict}, "
                        f"high_temp={result_high.verdict}). "
                        f"FAIL 판정 사유: {failed.reason}"
                    ),
                    "severity":    "MEDIUM",
                })
        else:
            # 단일 호출 모드 (CPU 환경 권장).
            # temp=0.0 으로 결정론적 판정. Self-Consistency 효과는 잃지만 latency 절반.
            raw = await client.generate(rendered, temperature=0.0)
            result = judge_engine._parse_llm_json_result(raw)

            if result.verdict == "FAIL":
                score = 1.0 - result.confidence
                violations.append({
                    "type":        "LLM_COMPLIANCE",
                    "description": result.reason,
                    "severity":    "HIGH" if result.confidence >= 0.8 else "MEDIUM",
                })
            else:
                score = result.confidence

        return {"llm_compliance_score": score, "llm_violations": violations}

    except Exception as e:
        # 일부 예외는 str(e) 가 비어있어 진단 불가 — type 도 함께 노출
        detail = f"{type(e).__name__}: {e}" if str(e) else type(e).__name__
        return {
            "llm_compliance_score": 0.5,
            "llm_violations": [
                {"type": "LLM_ERROR", "description": detail, "severity": "MEDIUM"}
            ],
        }


# ──────────────────────────────────────────────────────────────
# 노드 4: 위반 집계
# ──────────────────────────────────────────────────────────────
def violation_aggregator_node(state: ComplianceState) -> dict:
    """
    rule_violations + llm_violations 병합.
    동일 type 중복 제거 (더 높은 severity 유지).
    severity 내림차순 정렬 (HIGH → MEDIUM → LOW).
    """
    severity_rank = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    seen: dict[str, dict] = {}

    for v in (state.get("rule_violations", []) or []) + (state.get("llm_violations", []) or []):
        vtype = v.get("type", "UNKNOWN")
        if vtype not in seen:
            seen[vtype] = v
        else:
            if severity_rank.get(v.get("severity", "LOW"), 2) < severity_rank.get(
                seen[vtype].get("severity", "LOW"), 2
            ):
                seen[vtype] = v

    merged = sorted(
        seen.values(),
        key=lambda x: severity_rank.get(x.get("severity", "LOW"), 2),
    )
    return {"all_violations": merged}


# ──────────────────────────────────────────────────────────────
# 노드 5: 최종 액션 결정 (결정론적)
# ──────────────────────────────────────────────────────────────
def action_engine_node(state: ComplianceState) -> dict:
    """
    F2-1 fallback: rule_rejected 경로에서 violation_aggregator 우회 시
                   rule_violations + llm_violations 를 직접 결합.

    rule_rejected=True 또는 HIGH severity 위반 ≥ 1건  → REJECTED (final_score=0.0)
    MEDIUM 위반 존재 (HIGH 없음)                       → FLAGGED
    위반 없음                                          → APPROVED
    """
    rule_violations = state.get("rule_violations", []) or []
    llm_violations = state.get("llm_violations", []) or []

    aggregated = state.get("all_violations")
    if not aggregated:
        # rule_rejected 경로에서 violation_aggregator 가 우회된 경우 fallback
        aggregated = rule_violations + llm_violations

    has_high = any(v.get("severity") == "HIGH" for v in aggregated)
    has_medium = any(v.get("severity") == "MEDIUM" for v in aggregated)
    llm_score = state.get("llm_compliance_score", 1.0)

    if state.get("rule_rejected") or has_high:
        # REJECTED 시 final_score 는 0.0 (위반인데 LLM score가 높게 나오는 의미 모순 방지)
        return {
            "final_status":   "REJECTED",
            "final_score":    0.0,
            "all_violations": aggregated,
        }
    if has_medium:
        return {
            "final_status":   "FLAGGED",
            "final_score":    llm_score,
            "all_violations": aggregated,
        }
    return {
        "final_status":   "APPROVED",
        "final_score":    llm_score,
        "all_violations": aggregated,
    }


# ──────────────────────────────────────────────────────────────
# 노드 6: 감사 로그 저장
# ──────────────────────────────────────────────────────────────
def audit_logger_node(state: ComplianceState) -> dict:
    """
    response_audit_logs 테이블 INSERT (INSERT ONLY).
    audit_query_id로 Feature 1 감사 로그와 선택적 연결.
    PRD 5.2.6: 모든 평가 결과는 근거(violations)와 함께 저장.
    """
    audit_id = str(uuid.uuid4())
    # 다중 정책 적용 시: 첫 번째 정책 ID (시스템 정책) 를 대표 audit policy_id 로 저장.
    # 결합된 가상 정책 ID ("COMBINED:...") 는 실제 FK 가 아니므로 사용 불가.
    audit_policy_id = state.get("policy_id") or (state.get("policy_ids") or [None])[0]
    session = SessionLocal()
    try:
        masked_query, pii_q = mask_pii(state["query"])
        masked_response, pii_r = mask_pii(state["response"])
        merged_pii = pii_q + pii_r
        session.add(ResponseAuditLogModel(
            id=audit_id,
            trace_id=state.get("trace_id"),
            query_audit_id=state.get("audit_query_id"),
            agent_id=state["agent_id"],
            policy_id=audit_policy_id,
            policy_version=state.get("policy_version"),
            query=state["query"],
            masked_query=masked_query,
            response=state["response"],
            masked_response=masked_response,
            pii_detected=merged_pii or None,
            compliance_score=state.get("final_score", 0.0),
            status=state.get("final_status", "APPROVED"),
            violations=state.get("all_violations", []),
        ))
        session.commit()
        return {"audit_id": audit_id}
    except Exception as e:
        session.rollback()
        return {"audit_id": audit_id, "error_message": f"감사 로그 저장 실패: {e}"}
    finally:
        session.close()


# ──────────────────────────────────────────────────────────────
# 그래프 조립
# ──────────────────────────────────────────────────────────────
@lru_cache
def build_response_guard_graph():
    graph = StateGraph(ComplianceState)

    graph.add_node("policy_loader",        policy_loader_node)
    graph.add_node("rule_compliance",      rule_compliance_node)
    graph.add_node("llm_compliance_agent", llm_compliance_agent_node)
    graph.add_node("violation_aggregator", violation_aggregator_node)
    graph.add_node("action_engine",        action_engine_node)
    graph.add_node("audit_logger",         audit_logger_node)

    graph.set_entry_point("policy_loader")

    # 정책 로더 실패 → 즉시 action_engine (REJECTED, F2-1 fallback으로 violations 보존)
    graph.add_conditional_edges(
        "policy_loader",
        lambda s: "action_engine" if s.get("rule_rejected") else "rule_compliance",
        {"action_engine": "action_engine", "rule_compliance": "rule_compliance"},
    )
    # 룰 위반 확정 → LLM 생략 (비용 절감, F2-1 fallback으로 violations 보존)
    graph.add_conditional_edges(
        "rule_compliance",
        lambda s: "action_engine" if s.get("rule_rejected") else "llm_compliance_agent",
        {"action_engine": "action_engine", "llm_compliance_agent": "llm_compliance_agent"},
    )
    graph.add_edge("llm_compliance_agent", "violation_aggregator")
    graph.add_edge("violation_aggregator", "action_engine")
    graph.add_edge("action_engine",        "audit_logger")
    graph.add_edge("audit_logger",         END)

    return graph.compile()
