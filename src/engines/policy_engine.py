import json
import re
from typing import Tuple, Dict, Any, Optional

from src.schemas.policy import Policy, PolicyEvaluationResult


class PolicyEngine:
    """
    YAML로 정의된 거버넌스 정책을 로드하여 LLM의 응답을 평가하는 핵심 엔진입니다.

    성능 최적화 설계:
    1. 고속 문자열 매칭 로직을 무거운 정규식 검사보다 무조건 먼저 처리합니다.
    2. 첫 번째 위반이 발견되면 후속 검사를 즉시 중단하여 CPU 부하를 줄입니다.
    """

    def evaluate_policy(
        self,
        policy: Policy,
        response: str,
        context: dict,
        retrieved_context: list[str] | None,
    ) -> PolicyEvaluationResult:

        # 컨텍스트 의존 정책을 위한 사전 조건 검증
        if policy.preconditions and policy.preconditions.requires_retrieved_context:
            precondition_result = self._handle_preconditions(policy, retrieved_context)
            if precondition_result is not None:
                return precondition_result

        triggered = False
        judge_required = (policy.judge_required == "always")
        evidence_spans: list[dict] = []
        reason = "No violation detected."
        recommended_action = policy.action.type or policy.action.default_type or "LOG"

        for rule in policy.rules:
            if rule.condition == "contains_categorized_forbidden_terms":
                is_violated, span, rule_reason = self._evaluate_content_safety(rule, response, policy.id)

                if is_violated:
                    evidence_spans.append(span)
                    reason = rule_reason
                    triggered = True

                    # 위반 시 즉시 차단할지 Judge 엔진으로 넘겨 문맥을 확인할지 결정
                    if rule.on_rule_failure == "judge_fallback" or policy.judge_required == "rule_triggered":
                        judge_required = True
                    else:
                        judge_required = False
                    break

            elif rule.condition == "format_validation":
                is_violated, span, rule_reason = self._evaluate_format_compliance(rule, response, policy.id)

                if is_violated:
                    evidence_spans.append(span)
                    reason = rule_reason
                    triggered = True

                    if rule.on_rule_failure == "block_immediately":
                        judge_required = False
                    elif rule.on_rule_failure == "judge_fallback" or policy.judge_required == "rule_triggered":
                        judge_required = True
                    break

        if policy.judge_required == "always":
            judge_required = True
        elif policy.judge_required == "never":
            judge_required = False

        return PolicyEvaluationResult(
            policy_id=policy.id,
            policy_name=policy.name,
            triggered=triggered,
            judge_required=judge_required,
            recommended_action=recommended_action,
            severity=policy.severity,
            evidence_spans=evidence_spans,
            reason=reason,
        )

    def _handle_preconditions(
        self,
        policy: Policy,
        retrieved_context: list[str] | None
    ) -> Optional[PolicyEvaluationResult]:
        """
        사전 조건 처리 전용 메서드입니다.
        RAG 검색 결과가 비어있는 경우 정책에 정의된 동작 방식에 따라 결과를 라우팅합니다.
        """
        if not policy.preconditions:
            return None

        # 데이터가 아예 없거나 공백 문자열만 존재하는 무의미한 배열인 경우를 필터링
        context_missing = retrieved_context is None or len(retrieved_context) == 0
        context_empty = retrieved_context and all(
            not c or len(str(c).strip()) == 0 for c in retrieved_context
        )

        if context_missing or context_empty:
            behavior = policy.preconditions.no_context_behavior or "SKIP"

            if behavior == "SKIP":
                return self._create_skipped_result(
                    policy,
                    reason_msg="no_context_or_empty",
                    skip_reason="retrieved_context is missing or empty"
                )
            elif behavior == "WARN":
                # WARN 모드일 때는 감사 로그에 경고 내역이 정상 기록되어야 하므로 triggered를 True로 설정
                return PolicyEvaluationResult(
                    policy_id=policy.id,
                    policy_name=policy.name,
                    triggered=True,
                    judge_required=False,
                    recommended_action="LOG",
                    severity=policy.severity,
                    reason="No meaningful retrieved_context provided for groundedness check (WARN mode)",
                    skip_reason="no_meaningful_context"
                )
            elif behavior == "FAIL":
                # 필수 컨텍스트 없이 답변을 시도한 것 자체를 위험으로 간주하여 즉시 차단
                return PolicyEvaluationResult(
                    policy_id=policy.id,
                    policy_name=policy.name,
                    triggered=True,
                    judge_required=False,
                    recommended_action="BLOCK",
                    severity=policy.severity,
                    reason="Retrieved context required but missing or empty (FAIL mode)",
                    skip_reason="context_required_but_missing"
                )

        return None

    def _create_skipped_result(
        self,
        policy: Policy,
        reason_msg: str,
        skip_reason: Optional[str] = None
    ) -> PolicyEvaluationResult:
        """사전 조건 미충족으로 평가를 건너뛰는 경우 정상 통과와 구분하기 위해 스킵 사유를 반환합니다."""
        result = PolicyEvaluationResult(
            policy_id=policy.id,
            policy_name=policy.name,
            triggered=False,
            judge_required=False,
            recommended_action=policy.action.type or policy.action.default_type or "LOG",
            severity=policy.severity,
            reason=f"Preconditions not met, skipped evaluation. ({reason_msg})"
        )
        if skip_reason:
            result.skip_reason = skip_reason
        return result

    def _evaluate_content_safety(self, rule, response: str, policy_id: str) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        """
        안전성 룰 검사 메서드입니다.
        1. 빠른 문자열 검사를 먼저 수행하고 정규식 검사를 나중에 수행합니다.
        2. Rule 위반 후 Topical Exception과 High-Risk Intent를 분석하여 최종 판정합니다.
        """
        params = rule.parameters
        case_insensitive = params.get("case_insensitive", True)
        categories = params.get("categories", {})

        check_text = response.lower() if case_insensitive else response

        # [1차 검사] 리소스 소모가 적은 고속 문자열 검사 우선 실행
        for cat_name, cat_data in categories.items():
            if not cat_data.get("enabled", False):
                continue
            for term in cat_data.get("exact_terms", []):
                search_term = term.lower() if case_insensitive else term
                if search_term in check_text:
                    start = check_text.find(search_term)
                    span = {
                        "text": response[start:start + len(term)],
                        "start_char": start,
                        "end_char": start + len(term),
                        "source": "rule",
                        "condition": rule.condition,
                        "policy_id": policy_id,
                        "human_reason": f"Forbidden exact term detected: {term}"
                    }

                    # [Rule 위반 후 예외 처리]
                    # Topical Exception: 교육/연구/뉴스 등 주제적 논의는 허용
                    if self._has_topical_exception(response):
                        return False, None, ""

                    # High-Risk Intent: 실제 실행 방법/계획을 제공하려는 의도 감지 시 차단
                    if self._has_high_risk_intent(response):
                        return True, span, span["human_reason"]

                    # 모호한 경우: Judge에게 위임
                    return True, span, span["human_reason"]

        # [2차 검사] 1차 검사를 통과한 응답에 대해서만 복잡한 정규식 패턴 탐지 실행
        for cat_name, cat_data in categories.items():
            if not cat_data.get("enabled", False):
                continue
            patterns = cat_data.get("phrase_patterns", []) + cat_data.get("pii_patterns", [])
            flags = re.IGNORECASE if case_insensitive else 0

            for pattern in patterns:
                match = re.search(pattern, response, flags)
                if match:
                    span = {
                        "text": match.group(0),
                        "start_char": match.start(),
                        "end_char": match.end(),
                        "source": "rule",
                        "condition": rule.condition,
                        "policy_id": policy_id,
                        "human_reason": f"Forbidden pattern detected: {pattern}"
                    }

                    # [Rule 위반 후 예외 처리]
                    if self._has_topical_exception(response):
                        return False, None, ""

                    if self._has_high_risk_intent(response):
                        return True, span, span["human_reason"]

                    return True, span, span["human_reason"]

        return False, None, ""

    def _has_topical_exception(self, response: str) -> bool:
        """
        교육/연구/뉴스 등 주제적 논의(Topical)인 경우 완화 처리합니다.

        허용되는 맥락:
        - 교육: "마약의 위험성 교육", "테러 예방 교육"
        - 역사: "테러의 역사", "폭력 운동의 역사"
        - 뉴스: "최근 범죄 뉴스 보도"
        - 연구: "학술 논문에서의 폭력 분석"

        Returns:
            bool: Topical 예외 키워드가 포함되어 있으면 True
        """
        exception_terms = [
            "교육", "연구", "학술", "예방", "지원",
            "뉴스", "역사", "분석", "팩트체크", "임상",
            "치료", "정책 토론", "보안 인식", "윤리적", "비판"
        ]
        response_lower = response.lower()
        return any(term in response_lower for term in exception_terms)

    def _has_high_risk_intent(self, response: str) -> bool:
        """
        실제 실행 방법(Instruction), 계획 수립(Planning), 구체적 수단(Method)을
        제공하거나 조장하려는 의도를 감지합니다.

        차단되는 의도:
        - "마약을 만드는 구체적 방법"
        - "테러를 모의하는 단계별 계획"
        - "자살 방법 알려줘"

        Returns:
            bool: 높은 위험 의도가 감지되면 True
        """
        # [동사 기반 의도 검사] 사용자의 직접적인 요청 표현
        high_risk_verbs = [
            "만들어줘", "방법 알려줘", "계획 세워줘",
            "하는 법", "조장해", "도와줘", "단계별",
            "구체적으로", "상세히", "step by step"
        ]

        # [패턴 기반 의도 검사] HOW-TO 형식의 실행 지원 패턴
        high_risk_patterns = [
            r"(?i)how to",
            r"(?i)step by step",
            r"(?i)make.*tutorial",
            r"(?i)guide.*making",
            r"(?i)instructions? for",
            r"(?i)tutorial.*how"
        ]

        response_lower = response.lower()

        # 동사 기반 검사
        if any(verb in response_lower for verb in high_risk_verbs):
            return True

        # 패턴 기반 검사
        for pattern in high_risk_patterns:
            if re.search(pattern, response):
                return True

        return False

    def _evaluate_format_compliance(self, rule, response: str, policy_id: str) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        """
        출력 포맷 및 내용 준수 여부를 다각도로 검증합니다.

        검증 항목:
        1. 필수 포맷 충족 (JSON, MARKDOWN_TABLE)
        2. JSON 필수 키 존재 (answer, source, confidence 등)
        3. 진정한 Markdown Table 구조 (헤더 + 구분선)
        4. 금지 포맷 미포함 (JSON 외부의 마크다운 기호)
        """
        params = rule.parameters
        required = params.get("required_formats", [])
        forbidden = params.get("forbidden_formats", [])
        required_json_keys = params.get("required_json_keys", [])

        if required:
            passed_at_least_one = False
            errors = []

            if "JSON" in required:
                try:
                    parsed_json = json.loads(response)

                    # [강화된 검증] 단순 구문 파싱을 넘어 비즈니스에 필요한 필수 키가 존재하는지 내용까지 엄격하게 검증
                    if required_json_keys:
                        missing_keys = [k for k in required_json_keys if k not in parsed_json]
                        if missing_keys:
                            return self._create_format_span(
                                response, rule, policy_id,
                                f"Required JSON keys missing: {', '.join(missing_keys)}"
                            )
                    passed_at_least_one = True
                except json.JSONDecodeError:
                    errors.append("Not a valid JSON.")

            if "MARKDOWN_TABLE" in required and not passed_at_least_one:
                # [강화된 검증] 진정한 마크다운 테이블 구조 요구 (헤더 + 구분선 행)
                if self._is_real_markdown_table(response):
                    passed_at_least_one = True
                else:
                    errors.append("Not a valid MARKDOWN_TABLE.")

            if not passed_at_least_one:
                return self._create_format_span(response, rule, policy_id, f"Required format missing: {', '.join(errors)}")

        if "PLAIN_TEXT_WITH_MARKDOWN" in forbidden:
            # [충돌 해결] JSON 통과 여부에 따라 마크다운 기호 감지 범위 분리
            json_passed = required and "JSON" in required and self._is_valid_json(response)

            if json_passed:
                # JSON 내부 value의 마크다운 기호는 강조 용도의 정상적인 사용으로 간주
                # JSON 외부 텍스트의 마크다운 기호만 차단 (불필요한 설명 방지)
                if self._has_markdown_outside_json(response):
                    return self._create_format_span(response, rule, policy_id, "Forbidden markdown characters found outside JSON.")
            else:
                # JSON 포맷이 아닌 일반 텍스트 응답일 경우 마크다운 기호 사용을 전면 차단
                if re.search(r"[*#`]", response):
                    return self._create_format_span(response, rule, policy_id, "Forbidden markdown characters found.")

        return False, None, ""

    def _is_real_markdown_table(self, response: str) -> bool:
        """
        헤더 행과 구분선 행이 모두 존재하는 진정한 마크다운 표 구조인지 검증합니다.

        유효한 마크다운 테이블 형식:
        | 헤더1 | 헤더2 |
        |-------|-------|
        | 값1   | 값2   |

        오탐 방지:
        - 코드 블록의 파이프 기호
        - 주석 내 파이프 기호

        Args:
            response: 검증할 응답 텍스트

        Returns:
            bool: 진정한 마크다운 테이블 구조이면 True
        """
        lines = [l.strip() for l in response.split('\n') if l.strip().startswith('|')]
        if len(lines) < 2:
            return False
        # 구분선 행 패턴: |---|---|... 형태 (-, :, 공백만 포함)
        return bool(re.match(r'^\|[-\s:|]+\|$', lines[1]))

    def _is_valid_json(self, response: str) -> bool:
        """
        JSON 구문이 유효한지 검증합니다.

        Args:
            response: 검증할 응답 텍스트

        Returns:
            bool: 유효한 JSON 구문이면 True
        """
        try:
            json.loads(response)
            return True
        except json.JSONDecodeError:
            return False

    def _has_markdown_outside_json(self, response: str) -> bool:
        """
        JSON 객체 바깥 부분에 마크다운 기호나 불필요한 설명이 추가되었는지 확인합니다.

        허용되는 경우:
        - {"title": "# 제목", "value": "**강조**"}  ← JSON 내부이므로 허용

        차단되는 경우:
        - # 불필요한 설명
          {"answer": "test"}  ← JSON 외부에 마크다운 기호 있음

        Args:
            response: 검증할 응답 텍스트

        Returns:
            bool: JSON 외부에 마크다운 기호가 있으면 True
        """
        try:
            # JSON의 시작과 끝 위치 파악
            json_start = response.find('{')
            json_end = response.rfind('}') + 1 if response.rfind('}') != -1 else len(response)

            if json_start == -1 or json_end == 0:
                # JSON이 없으면 전체 텍스트 검사
                return bool(re.search(r"[*#`]", response))

            # JSON 앞뒤 텍스트만 검사
            before_json = response[:json_start]
            after_json = response[json_end:]
            outside_text = before_json + after_json

            return bool(re.search(r"[*#`]", outside_text))
        except:
            # 파싱 실패 시 보수적으로 전체 검사
            return bool(re.search(r"[*#`]", response))

    def _create_format_span(self, response: str, rule, policy_id: str, reason: str) -> Tuple[bool, Dict[str, Any], str]:
        """
        포맷 위반 시 문제 영역을 기록하기 위한 증거 객체를 생성합니다.

        Args:
            response: 원본 응답 텍스트
            rule: 적용된 Rule 객체
            policy_id: 정책 ID
            reason: 위반 사유

        Returns:
            Tuple[bool, Dict, str]: (위반여부, 증거객체, 사유)
        """
        span = {
            "text": response[:120],
            "start_char": 0,
            "end_char": min(len(response), 120),
            "source": "rule",
            "condition": rule.condition,
            "policy_id": policy_id,
            "human_reason": reason
        }
        return True, span, reason
