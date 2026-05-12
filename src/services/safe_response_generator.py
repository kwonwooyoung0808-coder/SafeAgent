"""Safe Response Generator (PRD §8).

차단/거부 시 사용자에게 단순한 거절 메시지 대신 안전하면서도 도움이 되는
대체 응답을 생성한다. 정책 위반 카테고리별로 차별화된 안내 문구를 제공해
사용자가 다음 행동을 결정할 수 있도록 한다.

설계:
- 1차: 위반 유형별 결정론적 템플릿 (빠른 응답, 외부 의존성 없음).
- 2차(선택): governance LLM 재호출로 자연어 표현 향상 — 비활성 (P95 영향).
"""
from __future__ import annotations

from typing import Iterable


# 위반 type prefix → 사용자용 친화적 안내 메시지
# F1 룰 엔진이 만들어내는 type 들 (FORBIDDEN_WORD, FORBIDDEN_PHRASE, JAILBREAK, PII)
# F2 노드들이 만들어내는 type 들 (LLM_COMPLIANCE, INCONSISTENT_RESPONSE, RULE 등)
_TEMPLATES: dict[str, str] = {
    "FORBIDDEN_WORD": (
        "죄송합니다. 입력하신 질문에 회사 정책상 허용되지 않은 표현이 포함되어 "
        "있어 답변드릴 수 없습니다. 표현을 다듬어 다시 질문해 주세요."
    ),
    "FORBIDDEN_PHRASE": (
        "죄송합니다. 입력하신 질문이 회사 정책상 금지된 주제에 해당해 "
        "답변드릴 수 없습니다. 다른 방식으로 질문해 주시면 도와드리겠습니다."
    ),
    "JAILBREAK": (
        "AI의 운영 지침을 변경하거나 우회하려는 요청에는 응답할 수 없습니다. "
        "원하시는 정보가 있다면 일반적인 형태로 다시 질문해 주세요."
    ),
    "PII": (
        "질문에 개인정보가 포함된 것으로 보입니다. 개인정보를 제거하고 다시 "
        "질문해 주시면 안전하게 답변드릴 수 있습니다."
    ),
    "POLICY_NOT_FOUND": (
        "현재 적용 가능한 정책이 설정되어 있지 않아 응답을 제공할 수 없습니다. "
        "관리자에게 문의해 주세요."
    ),
    "POLICY_LOAD_ERROR": (
        "정책 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."
    ),
    "LLM_COMPLIANCE": (
        "AI가 생성한 응답이 회사 정책을 충족하지 못해 사용자에게 전달되지 "
        "못했습니다. 질문을 더 구체적으로 작성해 주시면 정확한 답변을 "
        "제공해 드릴 수 있습니다."
    ),
    "INCONSISTENT_RESPONSE": (
        "AI 응답의 일관성을 검증하지 못해 안전을 위해 차단되었습니다. "
        "질문을 다시 시도해 주세요."
    ),
    "RULE": (
        "회사 응답 정책을 준수하지 못해 답변이 차단되었습니다. "
        "관련 부서 정책을 확인하거나 관리자에게 문의해 주세요."
    ),
}

_DEFAULT_BLOCKED = (
    "죄송합니다. 회사 정책상 이 질문에는 답변드릴 수 없습니다. "
    "다른 질문을 시도해 보시거나 관리자에게 문의해 주세요."
)

_DEFAULT_REJECTED = (
    "AI가 생성한 응답이 회사 정책을 통과하지 못해 차단되었습니다. "
    "질문을 다듬어 다시 시도하거나 관리자에게 문의해 주세요."
)


def _pick_primary_type(violations: Iterable[dict]) -> str | None:
    """HIGH severity 위반을 우선 선택. 그 다음 첫 번째 위반 type."""
    high = [v for v in violations if (v.get("severity") or "").upper() == "HIGH"]
    if high:
        return high[0].get("type")
    for v in violations:
        if v.get("type"):
            return v.get("type")
    return None


def generate_safe_response(
    *,
    stage: str,
    violations: list[dict] | None = None,
    risk_reasons: list[str] | None = None,
) -> str:
    """차단/거부 사유에 따라 사용자용 안전 대체 응답을 반환.

    Args:
        stage: "BLOCKED_BY_QUERY" | "REJECTED_BY_RESPONSE"
        violations: F2 violation dict 리스트 (type, severity, description)
        risk_reasons: F1 사유 텍스트 리스트 (룰 위반 포맷 문자열)

    Returns:
        사용자에게 그대로 노출 가능한 안전 메시지.
    """
    primary_type: str | None = None

    if violations:
        primary_type = _pick_primary_type(violations)

    if primary_type is None and risk_reasons:
        # F1 risk_reasons 는 "[FORBIDDEN_WORD/violence_hate] '테러' (severity=HIGH)" 같은 포맷
        for reason in risk_reasons:
            for key in _TEMPLATES:
                if key in reason:
                    primary_type = key
                    break
            if primary_type:
                break

    if primary_type and primary_type in _TEMPLATES:
        return _TEMPLATES[primary_type]

    return _DEFAULT_BLOCKED if stage == "BLOCKED_BY_QUERY" else _DEFAULT_REJECTED
