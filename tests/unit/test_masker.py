"""PII 마스커 단위 테스트."""
from __future__ import annotations

from src.utils.masker import mask_pii


def test_none_input_returns_none():
    masked, det = mask_pii(None)
    assert masked is None
    assert det == []


def test_no_pii_returns_unchanged():
    masked, det = mask_pii("오늘 날씨가 어떤가요?")
    assert masked == "오늘 날씨가 어떤가요?"
    assert det == []


def test_email_partial_mask():
    masked, det = mask_pii("연락처: user.test@example.com")
    assert "user.test" not in masked
    assert "@example.com" in masked  # 도메인은 보존
    assert masked.startswith("연락처: us")  # 앞 2글자 노출
    assert det == [{"type": "EMAIL", "count": 1}]


def test_short_email_local_full_mask():
    masked, det = mask_pii("ab@x.co")
    assert masked == "**@x.co"
    assert det[0]["type"] == "EMAIL"


def test_phone_kr_mobile():
    masked, det = mask_pii("연락처 010-1234-5678 입니다")
    assert "1234" not in masked
    assert "5678" in masked  # 마지막 4자리만 노출
    assert det == [{"type": "PHONE", "count": 1}]


def test_phone_kr_landline():
    masked, det = mask_pii("회사 02-123-4567")
    assert "4567" in masked
    assert "123" not in masked.replace("4567", "")
    assert det[0]["type"] == "PHONE"


def test_rrn_partial_mask():
    masked, det = mask_pii("주민번호 940101-1234567")
    assert "940101" in masked  # 앞 6자리 (생년월일) 보존
    assert "1234567" not in masked
    assert "940101-1******" in masked
    assert det == [{"type": "RRN", "count": 1}]


def test_credit_card_last_four_visible():
    masked, det = mask_pii("카드 1234-5678-9012-3456")
    assert "3456" in masked
    assert "1234-5678-9012" not in masked
    assert det == [{"type": "CARD", "count": 1}]


def test_ip_partial_mask():
    masked, det = mask_pii("접속 IP 192.168.1.100")
    assert "192" in masked
    assert "100" in masked
    assert "168" not in masked
    assert det == [{"type": "IP", "count": 1}]


def test_multiple_pii_types_all_detected():
    text = "이메일 a@b.co 전화 010-1234-5678 주민 940101-1234567"
    masked, det = mask_pii(text)
    assert "a@b.co" not in masked
    assert "1234-5678" not in masked
    assert "1234567" not in masked
    types = {d["type"] for d in det}
    assert types == {"EMAIL", "PHONE", "RRN"}


def test_multiple_same_type_counted():
    masked, det = mask_pii("a@x.co 와 b@y.co")
    email = [d for d in det if d["type"] == "EMAIL"][0]
    assert email["count"] == 2


def test_email_with_dots_in_local_part():
    masked, _ = mask_pii("first.last.name@company.co.kr")
    assert "@company.co.kr" in masked
    assert "first.last.name" not in masked
