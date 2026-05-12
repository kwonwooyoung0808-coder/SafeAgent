"""Safe Response Generator 단위 테스트 (PRD §8).

DB / LLM 의존 없는 순수 함수 검증:
- 위반 type 별 카테고리 매칭
- HIGH severity 우선 선택
- risk_reasons 텍스트에서 type 추출 (F1 fallback 경로)
- 매칭 실패 시 stage 별 기본 메시지
"""
from __future__ import annotations

from src.services.safe_response_generator import generate_safe_response


def test_forbidden_word_returns_word_template():
    msg = generate_safe_response(
        stage="BLOCKED_BY_QUERY",
        violations=[
            {"type": "FORBIDDEN_WORD", "severity": "HIGH", "category": "violence_hate"}
        ],
    )
    assert "허용되지 않은 표현" in msg


def test_jailbreak_returns_jailbreak_template():
    msg = generate_safe_response(
        stage="BLOCKED_BY_QUERY",
        violations=[{"type": "JAILBREAK", "severity": "HIGH"}],
    )
    assert "운영 지침" in msg or "우회" in msg


def test_pii_returns_pii_template():
    msg = generate_safe_response(
        stage="BLOCKED_BY_QUERY",
        violations=[{"type": "PII", "severity": "MEDIUM"}],
    )
    assert "개인정보" in msg


def test_high_severity_takes_priority_over_medium():
    """HIGH 위반이 있으면 MEDIUM 보다 먼저 선택된다."""
    msg = generate_safe_response(
        stage="BLOCKED_BY_QUERY",
        violations=[
            {"type": "PII", "severity": "MEDIUM"},
            {"type": "JAILBREAK", "severity": "HIGH"},
        ],
    )
    # JAILBREAK 템플릿이 선택되어야 함
    assert "운영 지침" in msg or "우회" in msg
    assert "개인정보" not in msg


def test_falls_back_to_risk_reasons_when_no_violations():
    """F1 router 는 violations 가 아닌 risk_reasons 텍스트만 넘기는 경우가 있음."""
    msg = generate_safe_response(
        stage="BLOCKED_BY_QUERY",
        violations=[],
        risk_reasons=["[FORBIDDEN_WORD/violence_hate] '테러' (severity=HIGH)"],
    )
    assert "허용되지 않은 표현" in msg


def test_unknown_type_uses_blocked_default_for_query_stage():
    msg = generate_safe_response(
        stage="BLOCKED_BY_QUERY",
        violations=[{"type": "UNKNOWN_NEW_RULE", "severity": "HIGH"}],
    )
    assert "회사 정책" in msg
    # 응답 단계 기본 문구가 섞이지 않아야 함
    assert "AI가 생성한" not in msg


def test_unknown_type_uses_rejected_default_for_response_stage():
    msg = generate_safe_response(
        stage="REJECTED_BY_RESPONSE",
        violations=[],
    )
    assert "AI가 생성한" in msg


def test_llm_compliance_returns_response_template():
    msg = generate_safe_response(
        stage="REJECTED_BY_RESPONSE",
        violations=[{"type": "LLM_COMPLIANCE", "severity": "HIGH"}],
    )
    assert "AI가 생성한 응답" in msg


def test_empty_inputs_return_default():
    msg = generate_safe_response(stage="BLOCKED_BY_QUERY")
    assert msg  # 비어있지 않음
    assert isinstance(msg, str)
