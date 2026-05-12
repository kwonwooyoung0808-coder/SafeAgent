"""Phase 4 인증 유틸리티.

- 비밀번호: bcrypt 직접 사용 (passlib 미사용 — deprecated)
- JWT: HS256 (PyJWT) — RFC 7518 §3.2 32B+ secret 강제 (config 검증)
- API Key: SHA-256 해시 — 평문은 발급 시점 1회만 노출, DB 엔 해시만 저장.
          검증은 hmac.compare_digest 로 상수시간 비교 (타이밍 공격 방어).

알고리즘 혼동 공격 대비: jwt.decode 시 algorithms=[settings.jwt_algorithm] 명시.
참고: bcrypt 는 비밀번호 72바이트 초과 시 잘림 — 운영 정책상 admin pw 가 그렇게
     길 일은 없으므로 별도 처리 안 함.
참고: refresh token 재사용/탈취 무효화는 별도 블랙리스트 테이블 도입 (Phase 5).
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

from src.core.config import get_settings


# ──────────────────────────────────────────────────────────────
# 비밀번호 (bcrypt rounds=12 — 의도적인 CPU 비용)
# ──────────────────────────────────────────────────────────────


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# ──────────────────────────────────────────────────────────────
# JWT (HS256) — Access / Refresh
# ──────────────────────────────────────────────────────────────


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(*, sub: str, role: str, policy_groups: list | None = None) -> str:
    """짧은 수명 (분 단위). API 호출 인증용."""
    s = get_settings()
    now = _now_utc()
    payload = {
        "sub": sub,
        "role": role,
        "policy_groups": policy_groups or [],
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=s.jwt_access_token_ttl_minutes)).timestamp()),
    }
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm)


def create_refresh_token(*, sub: str) -> str:
    """긴 수명 (일 단위). access token 갱신 전용 — role 정보 미포함."""
    s = get_settings()
    now = _now_utc()
    payload = {
        "sub": sub,
        "type": "refresh",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=s.jwt_refresh_token_ttl_days)).timestamp()),
    }
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm)


class TokenError(Exception):
    """JWT 검증 실패 (만료/서명 오류/형식 오류)."""


def decode_token(token: str, *, expected_type: str | None = None) -> dict[str, Any]:
    """JWT 디코드 + 만료/서명 검증. algorithms 명시로 혼동 공격 차단."""
    s = get_settings()
    try:
        payload = jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm])
    except jwt.ExpiredSignatureError as e:
        raise TokenError("token_expired") from e
    except jwt.InvalidTokenError as e:
        raise TokenError(f"invalid_token: {type(e).__name__}") from e

    if expected_type and payload.get("type") != expected_type:
        raise TokenError(f"wrong_token_type: expected {expected_type}")
    return payload


# ──────────────────────────────────────────────────────────────
# API Key (SHA-256 + hmac.compare_digest 검증)
# ──────────────────────────────────────────────────────────────


_API_KEY_PREFIX = "sak"  # SafeAgent Key — 운영자가 한눈에 식별 가능


def generate_api_key() -> tuple[str, str]:
    """평문 키와 SHA-256 해시를 함께 반환.

    평문은 발급 응답에 1회만 노출, DB 에는 해시만 저장.
    """
    raw = f"{_API_KEY_PREFIX}_{secrets.token_urlsafe(32)}"
    return raw, hash_api_key(raw)


def hash_api_key(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def verify_api_key(raw: str, stored_hash: str) -> bool:
    """상수시간 비교 (타이밍 공격 방어).

    호출 측에서 == 비교 금지 — 반드시 이 함수 사용.
    """
    return hmac.compare_digest(hash_api_key(raw), stored_hash)
