"""Phase 4 인증 유틸리티 단위 테스트.

검증:
  - bcrypt hash/verify
  - JWT 발급/검증/만료/타입 검사/algorithms 명시
  - API Key 생성 / SHA-256 해시 / 상수시간 비교
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from src.core.auth import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_api_key,
    hash_api_key,
    hash_password,
    verify_api_key,
    verify_password,
)
from src.core.config import get_settings


# ──────────────────────────────────────────────────────────────
# bcrypt
# ──────────────────────────────────────────────────────────────


def test_hash_password_then_verify_succeeds():
    h = hash_password("Hello12345!")
    assert h.startswith("$2b$")
    assert verify_password("Hello12345!", h) is True


def test_verify_password_wrong_pw_returns_false():
    h = hash_password("correct")
    assert verify_password("wrong", h) is False


def test_verify_password_invalid_hash_format_returns_false():
    """잘못된 형식 입력 시 예외 흘리지 않고 False — timing leak 회피."""
    assert verify_password("anything", "not-a-bcrypt-hash") is False
    assert verify_password("anything", "") is False


# ──────────────────────────────────────────────────────────────
# JWT
# ──────────────────────────────────────────────────────────────


def test_access_token_round_trip_payload_preserved():
    token = create_access_token(sub="u1", role="admin", policy_groups=["HR"])
    payload = decode_token(token, expected_type="access")
    assert payload["sub"] == "u1"
    assert payload["role"] == "admin"
    assert payload["policy_groups"] == ["HR"]
    assert payload["type"] == "access"
    assert "exp" in payload and "iat" in payload


def test_refresh_token_has_no_role_field():
    token = create_refresh_token(sub="u1")
    payload = decode_token(token, expected_type="refresh")
    assert payload["sub"] == "u1"
    assert payload["type"] == "refresh"
    assert "role" not in payload


def test_decode_token_wrong_type_raises():
    access = create_access_token(sub="u1", role="viewer")
    with pytest.raises(TokenError, match="wrong_token_type"):
        decode_token(access, expected_type="refresh")


def test_decode_token_invalid_signature_raises():
    settings = get_settings()
    forged = jwt.encode(
        {"sub": "x", "type": "access", "exp": int(time.time()) + 60},
        "different-secret-32-bytes-of-noise-padding-to-fit",
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(TokenError):
        decode_token(forged, expected_type="access")


def test_decode_token_expired_raises():
    settings = get_settings()
    expired = jwt.encode(
        {
            "sub": "u",
            "role": "admin",
            "policy_groups": [],
            "type": "access",
            "iat": int(time.time()) - 7200,
            "exp": int(time.time()) - 3600,
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(TokenError, match="token_expired"):
        decode_token(expired)


def test_decode_token_rejects_none_alg():
    """알고리즘 혼동 공격 차단 — alg=none 토큰은 거부되어야 함."""
    none_token = jwt.encode({"sub": "x", "type": "access"}, "", algorithm="none")
    with pytest.raises(TokenError):
        decode_token(none_token, expected_type="access")


# ──────────────────────────────────────────────────────────────
# API Key
# ──────────────────────────────────────────────────────────────


def test_generate_api_key_returns_raw_and_hash():
    raw, hashed = generate_api_key()
    assert raw.startswith("sak_")
    assert len(hashed) == 64  # SHA-256 hex
    assert hashed == hash_api_key(raw)


def test_verify_api_key_constant_time_comparison():
    raw, hashed = generate_api_key()
    assert verify_api_key(raw, hashed) is True
    assert verify_api_key("sak_wrong", hashed) is False


def test_generate_api_key_uniqueness():
    """동일 함수 호출 시 매번 다른 키."""
    keys = {generate_api_key()[0] for _ in range(50)}
    assert len(keys) == 50
