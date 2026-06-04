from __future__ import annotations

import re

# Phase 3-C: 한국어 조사/어미 목록 — 형태소 변형 검증에 사용
_KO_SUFFIXES: tuple[str, ...] = (
    "을", "를", "이", "가", "은", "는", "의", "에", "에서", "에게",
    "으로", "로", "과", "와", "도", "만", "까지", "부터", "보다",
    "처럼", "같이", "이나", "나", "이며", "며", "이고", "고",
    "이란", "란", "이라", "라", "으로서", "로서", "에도", "에서도",
)

# 한국어 단어 경계 패턴 (한글+영숫자 혼합 지원)
_WORD_BOUNDARY = re.compile(r"[\s,.;:!?()「」\[\]{}'\"\n\r]")


class GroundingValidator:
    """
    LLM이 추출한 값이 원본 문서에 실제로 존재하는지 검증.

    Pydantic 구조 검증(schema_validator_node)과 분리된 독립 레이어.
    - forbidden_words 환각 탐지 및 제거 (Phase 3-C: 형태소 변형 지원)
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

    # Fix 3: 어근 최소 길이 — 너무 짧은 어근은 흔한 단어와 충돌(예: "정보")
    _MIN_ROOT_LEN = 4

    def _word_in_text(self, word: str, text: str) -> bool:
        """
        Phase 3-C: 단어 또는 형태소 변형이 텍스트에 포함되는지 확인.

        탐지 순서:
        1. 정확 일치 (대소문자 무시)
        2. 어근에 다른 조사를 붙여서 검색 — LLM이 bare noun을 추출했을 때
        3. 조사 제거 후 어근 검색 — 단, 어근 길이 ≥ _MIN_ROOT_LEN (Fix 3)
           너무 짧은 어근(예: "정보")은 흔한 단어와 충돌하므로 제외

        Fix 3: 환각 탐지가 과하게 관대해지는 문제 방지.
        - "고객정보를"에서 "를" 제거 후 "고객정보" 검색 → OK (어근 4자)
        - "정보를"에서 "를" 제거 후 "정보" 검색 → REJECT (어근 2자, 너무 흔함)
        """
        word_lower = word.lower()
        text_lower = text.lower()

        # 1. 정확 일치
        if word_lower in text_lower:
            return True

        # 2. 어근에 다른 조사 붙여 검색 (LLM이 bare noun 추출한 경우)
        for suffix in self._KO_SUFFIXES_NO_ROOT_REDUCTION:
            variant = word_lower + suffix
            if variant in text_lower:
                return True

        # 3. 조사 제거 → 어근 검색 (단, 어근이 충분히 길어야 함)
        for suffix in _KO_SUFFIXES:
            if word_lower.endswith(suffix):
                root = word_lower[: -len(suffix)]
                if len(root) >= self._MIN_ROOT_LEN and root in text_lower:
                    return True

        return False

    # 짧은 조사만 사용 (어근 추가 검색용 — 어근 길이 제한 없이 안전)
    _KO_SUFFIXES_NO_ROOT_REDUCTION: tuple[str, ...] = (
        "을", "를", "이", "가", "은", "는", "의", "에", "에서",
        "으로", "로", "과", "와", "도", "만",
    )

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
            if self._word_in_text(word, raw_text):
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
