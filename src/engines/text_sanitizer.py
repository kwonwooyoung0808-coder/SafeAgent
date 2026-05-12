from __future__ import annotations

import re


class TextSanitizer:
    """
    .docx에서 추출된 텍스트를 LLM 프롬프트 인젝션 공격으로부터 보호.

    공격 벡터:
    - 흰색(FFFFFF) 폰트로 숨겨진 지시문
    - 본문 중간에 삽입된 "SYSTEM OVERRIDE: ..." 패턴
    - 정책 값(forbidden_words, action)을 직접 조작하는 텍스트

    처리 방식:
    - 탐지된 패턴을 [REDACTED-INJECTION-ATTEMPT]로 교체 (삭제 아님)
    - 탐지 목록을 반환해 감사 로그 기록
    """

    INJECTION_PATTERNS: list[str] = [
        r"(?i)(ignore|forget|override|disregard).{0,30}"
        r"(instruction|rule|policy|above|previous|system)",
        r"(?i)(you\s+are\s+now|act\s+as|pretend|roleplay|jailbreak)",
        r"(?i)(system\s*:?\s*override|system\s*prompt)",
        r"(?i)(new\s+instruction|updated\s+instruction)",
        r"(?i)forbidden_words\s*[:=]\s*\[\s*\]",
        r"(?i)on_forbidden_word\s*[:=]\s*['\"]?\s*log\s*['\"]?",
        r"(?i)(set\s+forbidden_words\s+to|change\s+action\s+to)",
        r"(?i)(disregard\s+all|ignore\s+all)\s+(previous|above|prior)",
    ]

    def sanitize(self, raw_text: str) -> tuple[str, list[str]]:
        """
        Returns:
            sanitized_text: 인젝션 패턴이 [REDACTED]로 교체된 텍스트
            detected: 탐지된 패턴 설명 목록 (비어 있으면 안전)
        """
        detected: list[str] = []
        sanitized = raw_text

        for pattern in self.INJECTION_PATTERNS:
            if re.search(pattern, sanitized, flags=re.IGNORECASE | re.DOTALL):
                detected.append(
                    f"SECURITY: 인젝션 패턴 탐지 → 패턴: '{pattern[:60]}'"
                )
                sanitized = re.sub(
                    pattern,
                    "[REDACTED-INJECTION-ATTEMPT]",
                    sanitized,
                    flags=re.IGNORECASE | re.DOTALL,
                )

        return sanitized, detected
