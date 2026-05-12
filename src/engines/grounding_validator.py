from __future__ import annotations


class GroundingValidator:
    """
    LLM이 추출한 값이 원본 문서에 실제로 존재하는지 검증.

    Pydantic 구조 검증(schema_validator_node)과 분리된 독립 레이어.
    - forbidden_words 환각 탐지 및 제거
    - severity 오분류 탐지 및 보수적 하향
    - actions 오추출 탐지 및 보수적 BLOCK 적용
    """

    SEVERITY_KEYWORDS: dict[str, list[str]] = {
        "HIGH":   ["높음", "high", "심각", "중대", "필수", "반드시", "절대", "엄격"],
        "MEDIUM": ["중간", "medium", "보통", "권고", "권장", "가급적", "중요"],
        "LOW":    ["낮음", "low", "참고", "선택", "경미", "권고사항"],
    }

    ACTION_KEYWORDS: dict[str, list[str]] = {
        "BLOCK":   ["차단", "금지", "block", "즉시 거부", "허용 안", "불허", "불가"],
        "LOG":     ["기록", "로그", "log", "경고", "모니터", "추적"],
        "FLAGGED": ["검토", "flag", "플래그", "보류", "검토 후"],
    }

    def validate_forbidden_words(
        self,
        extracted_words: list[str],
        raw_text: str,
    ) -> tuple[list[str], list[str]]:
        """
        Returns:
            verified_words: 원본 문서에 실제로 존재하는 금지어
            hallucinated_words: 원본에 없는 환각 금지어 (제거 대상)
        """
        verified: list[str] = []
        hallucinated: list[str] = []
        for word in extracted_words:
            if word.lower() in raw_text.lower():
                verified.append(word)
            else:
                hallucinated.append(word)
        return verified, hallucinated

    def validate_severity_grounding(
        self,
        compliance_checks: list[dict],
        raw_text: str,
    ) -> tuple[list[dict], list[str]]:
        """
        severity가 원본 문서 근처(window=200자)에 명시되지 않으면
        보수적으로 MEDIUM으로 하향 조정.

        Returns:
            validated_checks: severity가 보정된 준수 항목 목록
            warnings: 보정 발생 항목 경고 메시지
        """
        warnings: list[str] = []
        validated: list[dict] = []

        for check in compliance_checks:
            claimed = check.get("severity", "HIGH")
            keywords = self.SEVERITY_KEYWORDS.get(claimed, [])
            context = self._extract_context(
                check.get("description", ""), raw_text, window=200
            )
            if context and not any(kw in context.lower() for kw in keywords):
                warnings.append(
                    f"severity '{claimed}' → '{check.get('id', '?')}' "
                    f"근처에 명시 없음. MEDIUM으로 보수적 처리. 수동 검토 필요."
                )
                check = {**check, "severity": "MEDIUM"}
            validated.append(check)

        return validated, warnings

    def validate_actions(
        self,
        actions: dict,
        raw_text: str,
    ) -> tuple[dict, list[str]]:
        """
        actions 값이 원본 문서의 처리 방식과 일치하는지 검증.
        명시되지 않은 경우 보수적으로 BLOCK 적용.

        Returns:
            validated_actions: 보정된 액션 dict
            warnings: 보정 발생 경고 메시지
        """
        warnings: list[str] = []
        validated = dict(actions)

        for action_key, action_val in actions.items():
            keywords = self.ACTION_KEYWORDS.get(action_val, [])
            if not any(kw in raw_text.lower() for kw in keywords):
                warnings.append(
                    f"action '{action_key}={action_val}'이 원본 문서에 "
                    f"명시되지 않음 → BLOCK으로 보수적 처리."
                )
                validated[action_key] = "BLOCK"

        return validated, warnings

    def _extract_context(
        self, keyword: str, text: str, window: int = 200
    ) -> str:
        """keyword 주변 window 범위 텍스트 추출."""
        idx = text.lower().find(keyword.lower())
        if idx == -1:
            return ""
        return text[max(0, idx - window): min(len(text), idx + window)]
