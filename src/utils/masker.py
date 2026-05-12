"""PII 마스킹 유틸리티 (PRD §6).

audit log / violation_report 에 저장되는 query/response 의 민감 정보를
정규식으로 탐지해 마스킹된 사본을 함께 저장한다.

설계:
- 원본은 query/response 컬럼에 그대로 보존 (감사 추적 + 디버깅용)
- 마스킹된 버전은 masked_query/masked_response 에 별도 저장
- 일반 운영자/감사자에게는 마스킹된 버전을 우선 노출, 원본은 별도 권한

탐지 카테고리:
- EMAIL : RFC 5322 단순화 패턴
- PHONE : 한국 휴대폰/일반 (010-1234-5678, 02-123-4567 등)
- RRN   : 주민등록번호 (940101-1234567)
- CARD  : 신용카드 (1234-5678-9012-3456 / 1234567890123456)
- IP    : IPv4 주소

마스킹 전략:
- 부분 마스킹 (식별 가능한 일부만 노출). 예: "user.****@example.com"
- 검색 가능성 보존 — 길이/구조 유지
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class _PIIRule:
    name: str
    pattern: re.Pattern[str]
    masker: callable  # (match) -> str


def _mask_email(m: re.Match[str]) -> str:
    local, domain = m.group(0).split("@", 1)
    if len(local) <= 2:
        return "*" * len(local) + "@" + domain
    return local[:2] + "*" * (len(local) - 2) + "@" + domain


def _mask_phone(m: re.Match[str]) -> str:
    s = m.group(0)
    digits = re.sub(r"\D", "", s)
    if len(digits) < 4:
        return "*" * len(s)
    # 마지막 4자리 노출, 나머지 마스킹 (구분자 위치 유지)
    visible_tail = digits[-4:]
    out = []
    tail_idx = 0
    for ch in s:
        if ch.isdigit():
            # 뒤에서부터 4개만 노출
            remaining_digits = sum(1 for c in s[len(out):] if c.isdigit())
            if remaining_digits <= 4:
                out.append(visible_tail[4 - remaining_digits])
            else:
                out.append("*")
        else:
            out.append(ch)
    return "".join(out)


def _mask_rrn(m: re.Match[str]) -> str:
    s = m.group(0)
    # 940101-1234567 → 940101-1******
    parts = s.split("-")
    if len(parts) == 2:
        return f"{parts[0]}-{parts[1][0]}{'*' * (len(parts[1]) - 1)}"
    return "*" * len(s)


def _mask_card(m: re.Match[str]) -> str:
    s = m.group(0)
    digits = re.sub(r"\D", "", s)
    if len(digits) < 4:
        return "*" * len(s)
    # 마지막 4자리만 노출
    visible_tail = digits[-4:]
    out = []
    digit_idx = 0
    total_digits = len(digits)
    for ch in s:
        if ch.isdigit():
            digit_idx += 1
            if digit_idx > total_digits - 4:
                out.append(visible_tail[digit_idx - (total_digits - 4) - 1])
            else:
                out.append("*")
        else:
            out.append(ch)
    return "".join(out)


def _mask_ip(m: re.Match[str]) -> str:
    parts = m.group(0).split(".")
    if len(parts) == 4:
        return f"{parts[0]}.*.*.{parts[3]}"
    return "*" * len(m.group(0))


_RULES: list[_PIIRule] = [
    _PIIRule(
        name="EMAIL",
        pattern=re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"),
        masker=_mask_email,
    ),
    _PIIRule(
        name="RRN",
        pattern=re.compile(r"\b\d{6}-\d{7}\b"),
        masker=_mask_rrn,
    ),
    _PIIRule(
        name="CARD",
        pattern=re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b"),
        masker=_mask_card,
    ),
    _PIIRule(
        name="PHONE",
        # 010-1234-5678 / 02-123-4567 / +82-10-1234-5678 / 01012345678
        pattern=re.compile(
            r"(?<!\d)(?:\+?\d{1,3}[-\s]?)?(?:0\d{1,2}[-\s]?)\d{3,4}[-\s]?\d{4}(?!\d)"
        ),
        masker=_mask_phone,
    ),
    _PIIRule(
        name="IP",
        pattern=re.compile(
            r"\b(?:25[0-5]|2[0-4]\d|[01]?\d\d?)(?:\.(?:25[0-5]|2[0-4]\d|[01]?\d\d?)){3}\b"
        ),
        masker=_mask_ip,
    ),
]


def mask_pii(text: str | None) -> tuple[str | None, list[dict]]:
    """텍스트에서 PII 를 탐지해 마스킹된 텍스트 + 탐지 항목 리스트 반환.

    Returns:
        (masked_text, detected) — text 가 None 이면 (None, []).
        detected 의 각 항목: {"type": "EMAIL", "count": 2}
    """
    if text is None:
        return None, []

    masked = text
    detected: list[dict] = []

    for rule in _RULES:
        matches = list(rule.pattern.finditer(masked))
        if matches:
            detected.append({"type": rule.name, "count": len(matches)})
            masked = rule.pattern.sub(rule.masker, masked)

    return masked, detected
