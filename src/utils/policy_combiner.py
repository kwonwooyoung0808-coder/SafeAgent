"""
다중 정책 결합 유틸리티 (Feature 2 전용).

Stage A 분리 전략:
- F1 은 시스템 입력 정책 1개만 사용 (combiner 미사용)
- F2 는 시스템 정책 + agent 의 부서별 정책을 결합한 가상 정책으로 평가

결합 규칙:
- rules: 모든 정책의 룰을 단순 연결 (위반 탐지 = OR 결합)
- severity: 가장 엄격한 값 (high > medium > low)
- priority: 가장 높은 값
- judge_required: "always" 우선, 다음 "rule_triggered", 마지막 "never"
- action: BLOCK 우선, 없으면 LOG
- judge.criteria: 모든 정책의 criteria 를 줄바꿈으로 합침 (LLM Judge 가 모두 평가)
"""
from __future__ import annotations

from src.schemas.policy import Policy, PolicyAction, PolicyJudgeConfig

_SEVERITY_RANK = {"low": 0, "medium": 1, "high": 2}
_JUDGE_REQUIRED_RANK = {"never": 0, "rule_triggered": 1, "always": 2}


def combine_policies(policies: list[Policy]) -> Policy:
    """
    여러 정책을 하나의 가상 정책으로 결합.

    기존 PolicyEngine / JudgeEngine 이 단일 Policy 객체를 기대하므로,
    결합된 가상 정책을 만들어 호환성 유지.
    """
    if not policies:
        raise ValueError("combine_policies: 빈 리스트")
    if len(policies) == 1:
        return policies[0]

    # rules: 단순 연결
    combined_rules = []
    for p in policies:
        combined_rules.extend(p.rules or [])

    # severity: 최댓값
    strictest_severity = max(policies, key=lambda p: _SEVERITY_RANK.get(p.severity, 1)).severity

    # priority: 최댓값
    highest_priority = max((p.priority for p in policies), default=100)

    # judge_required: 가장 엄격한 정책 우선
    strictest_judge_required = max(
        policies, key=lambda p: _JUDGE_REQUIRED_RANK.get(p.judge_required, 0)
    ).judge_required

    # type: 가장 엄격 (rule < hybrid < judge 가 의미상 자연스러우나
    #       엔진 동작상 hybrid 가 가장 호환성 좋음 → rule + judge 조합 시 hybrid)
    types = {p.type for p in policies}
    if "judge" in types and "rule" in types:
        combined_type = "hybrid"
    elif "judge" in types:
        combined_type = "judge"
    elif "hybrid" in types:
        combined_type = "hybrid"
    else:
        combined_type = "rule"

    # action: BLOCK 우선
    has_block = any((p.action.type == "BLOCK" or p.action.default_type == "BLOCK") for p in policies)
    base_action = next((p.action for p in policies if p.action.type == "BLOCK"), None) or policies[0].action
    combined_action = PolicyAction(
        message=base_action.message,
        type="BLOCK" if has_block else (base_action.type or base_action.default_type or "LOG"),
        fallback_response=base_action.fallback_response,
        default_type=base_action.default_type,
        block_threshold=base_action.block_threshold,
        block_message=base_action.block_message,
        log_message=base_action.log_message,
    )

    # judge: criteria 결합 (활성화된 것만)
    enabled_judges = [p.judge for p in policies if p.judge.enabled and p.judge.criteria]
    if enabled_judges:
        combined_criteria = "\n\n---\n\n".join(
            f"[정책 평가 기준 — {i+1}]\n{j.criteria}"
            for i, j in enumerate(enabled_judges)
        )
        # output_contract 는 첫 번째 enabled judge 의 것을 사용
        combined_judge = PolicyJudgeConfig(
            enabled=True,
            score_field=enabled_judges[0].score_field,
            criteria=combined_criteria,
            output_contract=enabled_judges[0].output_contract,
        )
    else:
        combined_judge = PolicyJudgeConfig(enabled=False)

    # severity_threshold: 가장 보수적 (high) 사용
    severity_thresholds = [p.severity_threshold for p in policies if p.severity_threshold]
    combined_threshold = "high" if "high" in severity_thresholds else (severity_thresholds[0] if severity_thresholds else None)

    return Policy(
        id="COMBINED:" + "+".join(p.id for p in policies),
        name=" + ".join(p.name for p in policies),
        version="combined",
        enabled=True,
        type=combined_type,
        severity=strictest_severity,
        priority=highest_priority,
        judge_required=strictest_judge_required,
        severity_threshold=combined_threshold,
        preconditions=policies[0].preconditions,
        rules=combined_rules,
        judge=combined_judge,
        action=combined_action,
        severity_by_confidence=policies[0].severity_by_confidence,
        conflict_resolution=policies[0].conflict_resolution,
    )
