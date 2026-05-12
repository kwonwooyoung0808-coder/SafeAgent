from __future__ import annotations

import re
import uuid
from functools import lru_cache

from langgraph.graph import END, StateGraph

from src.database.connection import SessionLocal
from src.database.models import QueryAuditLogModel
from src.schemas.query_risk import QueryRiskState
from src.utils.masker import mask_pii
from src.utils.policy_cache import get_policy_cache


# ──────────────────────────────────────────────────────────────
# 노드 1: 정책 로더 (DB → yaml_path → Policy 객체)
# ──────────────────────────────────────────────────────────────
def policy_loader_node(state: QueryRiskState) -> dict:
    """
    DB의 policies 테이블에서 policy_id로 yaml_path 조회.
    is_active=TRUE인 정책만 허용.
    Phase 3-A: 활성 PolicyVersion 조회해 audit 기록용 version 문자열을 state 에 저장.
    실패 → rule_blocked=True (Fail-Safe BLOCKED).
    """
    from src.database.models import PolicyModel, PolicyVersionModel
    session = SessionLocal()
    try:
        row = session.query(PolicyModel).filter(
            PolicyModel.id == state["policy_id"],
            PolicyModel.is_active == True,
        ).first()

        if not row:
            return {
                "error_message": f"policy_id={state['policy_id']} 활성 정책 없음",
                "rule_blocked":  True,
                "rule_violations": [{
                    "type": "POLICY_NOT_FOUND",
                    "matched": state["policy_id"],
                    "severity": "HIGH",
                }],
            }

        # 현재 활성 버전 조회 (없으면 PolicyModel.version 으로 fallback)
        ver_row = session.query(PolicyVersionModel).filter(
            PolicyVersionModel.policy_id == state["policy_id"],
            PolicyVersionModel.is_current == True,
        ).first()
        version = ver_row.version if ver_row else row.version

        # Phase 3-B: 캐시 경유 (디스크 I/O 1회/버전)
        policy = get_policy_cache().get(state["policy_id"], version, row.yaml_path)
        return {"policy": policy.model_dump(), "policy_version": version}

    except Exception as e:
        return {
            "error_message": str(e),
            "rule_blocked": True,
            "rule_violations": [{
                "type": "POLICY_LOAD_ERROR",
                "matched": str(e)[:200],
                "severity": "HIGH",
            }],
        }
    finally:
        session.close()


# ──────────────────────────────────────────────────────────────
# 룰 엔진 헬퍼: 단어 경계 매칭 (영문) vs substring (한국어)
# ──────────────────────────────────────────────────────────────
def _term_matches(term: str, query: str, case_insensitive: bool = True) -> bool:
    """
    ASCII 전용 단어는 \\b 경계 적용 → 'kill'이 'skillet'에 매칭되지 않게 함.
    한국어/혼합 단어는 substring 매칭 (한글에는 자연스러운 단어 경계 없음).
    """
    if not term:
        return False
    flags = re.IGNORECASE if case_insensitive else 0
    if all(ord(c) < 128 for c in term):
        # ASCII only — word boundary
        pattern = r"\b" + re.escape(term) + r"\b"
        return bool(re.search(pattern, query, flags=flags))
    # Korean / mixed — substring
    if case_insensitive:
        return term.lower() in query.lower()
    return term in query


def _safe_regex_search(pattern: str, query: str) -> bool:
    """잘못된 정규식 패턴이 있어도 워크플로우 전체가 깨지지 않도록 격리."""
    try:
        return bool(re.search(pattern, query))
    except re.error:
        return False


# ──────────────────────────────────────────────────────────────
# Jailbreak 패턴 (영문 + 한국어) — PRD 5.1.2: BLOCK
# ──────────────────────────────────────────────────────────────
_JAILBREAK_PATTERNS: list[str] = [
    # 영문
    r"(?i)ignore\s+(previous|above|all)\s+(instruction|rule|policy|prompt)",
    r"(?i)disregard\s+(all|previous|above)\s+(instruction|rule|prompt)",
    r"(?i)act\s+as\s+(if\s+you\s+are|a|an)",
    r"(?i)you\s+are\s+now\s+(a|an|the)",
    r"(?i)(pretend|imagine|roleplay).*(no\s+restriction|no\s+limit|no\s+filter)",
    r"(?i)bypass\s+(all|the)\s+(restriction|filter|safety|guardrail)",
    # 한국어 — 한국어 조사(을/를/은/는/이/가)는 (?:을|를|은|는|이|가)? 로 흡수
    r"(이전|위의?|앞의?)\s*(지시|규칙|정책|명령|프롬프트)(?:을|를|은|는|이|가)?\s*(무시|잊|벗어)",
    r"(너|당신|네)\s*(는|은)?\s*(이제|지금부터)\s*(다른|새로운)?\s*(AI|역할|페르소나|봇)",
    r"(제약|제한|규칙|가이드라인)(?:을|를|은|는|이|가)?\s*(풀고|해제|무력화|벗어나|우회)",
    r"(역할|페르소나|캐릭터)\s*(놀이|플레이|연기)",
]


# ──────────────────────────────────────────────────────────────
# 노드 2: 룰 엔진 (결정론적 — LLM 독립)
# ──────────────────────────────────────────────────────────────
# PRD 5.1.2 매핑:
#   Forbidden Words / Phrase Patterns → BLOCK (HIGH)
#   Jailbreak Patterns                → BLOCK (HIGH)
#   PII Patterns                      → LOG+WARN (MEDIUM, blocked=False)
def rule_engine_node(state: QueryRiskState) -> dict:
    """
    정책의 카테고리별 forbidden_words / phrase_patterns / pii_patterns 를 평가.
    HIGH 위반 → rule_blocked=True (LLM 우회). MEDIUM (PII) → blocked=False, LLM 계속.
    """
    query = state.get("query", "")
    policy = state.get("policy", {})
    violations: list[dict] = []
    blocked = False  # HIGH severity 위반 발견 시에만 True

    # ── ① 정책 기반: forbidden_words / phrase_patterns / pii_patterns ──
    for rule in policy.get("rules", []):
        if rule.get("condition") != "contains_categorized_forbidden_terms":
            continue
        params = rule.get("parameters", {}) or {}
        case_insensitive = params.get("case_insensitive", True)
        categories = params.get("categories", {}) or {}

        for cat_name, cat in categories.items():
            if not cat.get("enabled", True):
                continue  # ⚠️ enabled=false 카테고리는 건너뜀

            # 1a. exact_terms — HIGH severity
            if not blocked:
                for term in cat.get("exact_terms", []) or []:
                    if _term_matches(term, query, case_insensitive):
                        violations.append({
                            "type": "FORBIDDEN_WORD",
                            "category": cat_name,
                            "matched": term,
                            "severity": "HIGH",
                        })
                        blocked = True
                        break

            # 1b. phrase_patterns (정규식) — HIGH severity
            if not blocked:
                for pattern in cat.get("phrase_patterns", []) or []:
                    if _safe_regex_search(pattern, query):
                        violations.append({
                            "type": "FORBIDDEN_PHRASE",
                            "category": cat_name,
                            "matched": pattern[:80],
                            "severity": "HIGH",
                        })
                        blocked = True
                        break

            # 1c. pii_patterns (정규식) — PRD 5.1.2: LOG+WARN, BLOCK 아님
            for pattern in cat.get("pii_patterns", []) or []:
                if _safe_regex_search(pattern, query):
                    violations.append({
                        "type": "PII",
                        "category": cat_name,
                        "matched": pattern[:80],
                        "severity": "MEDIUM",  # ⚠️ blocked=False 유지
                    })
                    # 같은 카테고리에서 PII 한 번 잡으면 중복 방지로 break
                    break

    # ── ② Jailbreak 패턴 (정책과 별개로 항상 검사) ──
    if not blocked:
        for pattern in _JAILBREAK_PATTERNS:
            if _safe_regex_search(pattern, query):
                violations.append({
                    "type": "JAILBREAK",
                    "matched": pattern[:80],
                    "severity": "HIGH",
                })
                blocked = True
                break

    return {"rule_violations": violations, "rule_blocked": blocked}


# ──────────────────────────────────────────────────────────────
# Phase 1 — F1 LLM 제거 (PRD §5.1: P95 ≤ 3s 요구)
# 사용자 입력 검사는 결정론적 룰만 사용. 의미론적 위험 판단은
# F2 응답 검증의 LLM Judge 단계에서만 수행 (응답이 위험을 증폭한 경우 차단).
# ──────────────────────────────────────────────────────────────


# ──────────────────────────────────────────────────────────────
# 룰 위반을 사람이 읽기 좋은 텍스트로 변환
# ──────────────────────────────────────────────────────────────
def _format_rule_violation(v: dict) -> str:
    vtype = v.get("type", "RULE")
    matched = v.get("matched", "")
    category = v.get("category", "")
    sev = v.get("severity", "HIGH")
    if category:
        return f"[{vtype}/{category}] '{matched}' (severity={sev})"
    return f"[{vtype}] '{matched}' (severity={sev})"


# ──────────────────────────────────────────────────────────────
# 노드 4: 액션 결정 (결정론적)
# ──────────────────────────────────────────────────────────────
def action_engine_node(state: QueryRiskState) -> dict:
    """
    Phase 1: F1 LLM 제거 후 결정론적 룰 기반 판정.

    BLOCK : rule_blocked=True (HIGH severity 위반)
    WARN  : MEDIUM rule violation 존재 (예: PII)
    PASS  : 위반 없음

    combined_reasons 는 rule_violations 텍스트만 포함 (응답 + audit 공통).
    """
    rule_blocked = state.get("rule_blocked", False)
    rule_violations = state.get("rule_violations", []) or []

    combined = [_format_rule_violation(v) for v in rule_violations]

    has_medium_rule = any(
        v.get("severity") == "MEDIUM" for v in rule_violations
    )

    if rule_blocked:
        return {
            "final_status":     "BLOCKED",
            "final_score":      1.0,
            "action_taken":     "BLOCK",
            "combined_reasons": combined,
        }
    if has_medium_rule:
        return {
            "final_status":     "WARNED",
            "final_score":      0.5,
            "action_taken":     "LOG",
            "combined_reasons": combined,
        }
    return {
        "final_status":     "PASSED",
        "final_score":      0.0,
        "action_taken":     "PASS",
        "combined_reasons": combined,
    }


# ──────────────────────────────────────────────────────────────
# 노드 5: 감사 로그 저장
# ──────────────────────────────────────────────────────────────
def audit_logger_node(state: QueryRiskState) -> dict:
    """
    query_audit_logs 테이블 INSERT (INSERT ONLY).
    risk_reasons 컬럼에는 룰 위반 + LLM 사유 합본 저장 → 사후 감사 시 차단 근거 추적 가능.
    """
    audit_id = str(uuid.uuid4())
    masked_query, pii_detected = mask_pii(state["query"])
    session = SessionLocal()
    try:
        session.add(QueryAuditLogModel(
            id=audit_id,
            trace_id=state.get("trace_id"),
            agent_id=state["agent_id"],
            policy_id=state["policy_id"],
            policy_version=state.get("policy_version"),
            query=state["query"],
            masked_query=masked_query,
            pii_detected=pii_detected,
            context=state.get("context"),
            risk_score=state.get("final_score", 0.0),
            status=state.get("final_status", "PASSED"),
            risk_reasons=state.get("combined_reasons", []),
            action_taken=state.get("action_taken", "PASS"),
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
def build_input_guard_graph():
    graph = StateGraph(QueryRiskState)

    graph.add_node("policy_loader",  policy_loader_node)
    graph.add_node("rule_engine",    rule_engine_node)
    graph.add_node("action_engine",  action_engine_node)
    graph.add_node("audit_logger",   audit_logger_node)

    graph.set_entry_point("policy_loader")

    # 정책 로더 실패 → 바로 action_engine (Fail-Safe BLOCKED)
    graph.add_conditional_edges(
        "policy_loader",
        lambda s: "action_engine" if s.get("rule_blocked") else "rule_engine",
        {"action_engine": "action_engine", "rule_engine": "rule_engine"},
    )
    # F1 룰 평가 후 곧바로 액션 결정 (LLM 미사용 — Phase 1 성능 최적화)
    graph.add_edge("rule_engine",    "action_engine")
    graph.add_edge("action_engine",  "audit_logger")
    graph.add_edge("audit_logger",   END)

    return graph.compile()
