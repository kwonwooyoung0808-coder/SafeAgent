"""Phase 4: 인증 — login / refresh / me / password.

NIST SP 800-228 REC-API-11: 사람 신원은 JWT 로 식별.
HS256 (RFC 7518) — 단일 조직 내부 시스템 가정.

Phase 5 예정 보강 (현재 미구현):
  - Rate limiting / account lockout (slowapi + 실패 카운트)
  - Refresh token rotation (refresh_tokens 테이블 + jti 추적)
  - 비밀번호 변경 시 기존 세션 무효화 (password_changed_at + iat 비교)
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from src.core.auth import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from src.core.config import get_settings
from src.core.dependencies import AuthenticatedUser, get_current_user, get_db
from src.database.models import UserModel

router = APIRouter(prefix="/v1/auth", tags=["auth"])


# ──────────────────────────────────────────────────────────────
# 스키마
# ──────────────────────────────────────────────────────────────


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=512)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # access_token TTL (초)


class RefreshRequest(BaseModel):
    refresh_token: str


class AccessOnly(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class MeResponse(BaseModel):
    user_id: str
    username: str
    role: str
    policy_groups: list


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=512)
    new_password: str = Field(min_length=12, max_length=512)

    @field_validator("new_password")
    @classmethod
    def _complexity(cls, v: str) -> str:
        # 최소: 글자 1자 + 숫자 1자. 기호/대소문자 강제는 다국어 환경 대비 생략.
        if not re.search(r"[A-Za-z]", v):
            raise ValueError("password_must_include_letter")
        if not re.search(r"\d", v):
            raise ValueError("password_must_include_digit")
        return v


# ──────────────────────────────────────────────────────────────
# 엔드포인트
# ──────────────────────────────────────────────────────────────


@router.post("/login", response_model=TokenPair)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenPair:
    """username + password 검증 후 access/refresh 토큰 쌍 발급.

    실패 시 401 (사유 무차별 동일 — 사용자 enumeration 방지).
    """
    s = get_settings()
    if s.demo_auth_bypass:
        return TokenPair(
            access_token=create_access_token(sub="demo-admin", role="admin", policy_groups=[]),
            refresh_token=create_refresh_token(sub="demo-admin"),
            expires_in=s.jwt_access_token_ttl_minutes * 60,
        )

    user = db.query(UserModel).filter(UserModel.username == payload.username).first()
    if (
        not user
        or not user.is_active
        or not verify_password(payload.password, user.hashed_password)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_credentials",
        )

    return TokenPair(
        access_token=create_access_token(
            sub=user.id, role=user.role, policy_groups=user.policy_groups or []
        ),
        refresh_token=create_refresh_token(sub=user.id),
        expires_in=s.jwt_access_token_ttl_minutes * 60,
    )


@router.post("/refresh", response_model=AccessOnly)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)) -> AccessOnly:
    """refresh_token 으로 새 access_token 발급. role/policy_groups 는 DB 에서 재조회."""
    s = get_settings()
    if s.demo_auth_bypass:
        return AccessOnly(
            access_token=create_access_token(sub="demo-admin", role="admin", policy_groups=[]),
            expires_in=s.jwt_access_token_ttl_minutes * 60,
        )

    try:
        decoded = decode_token(payload.refresh_token, expected_type="refresh")
    except TokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )

    user = db.query(UserModel).filter(UserModel.id == decoded["sub"]).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="user_inactive_or_deleted",
        )

    return AccessOnly(
        access_token=create_access_token(
            sub=user.id, role=user.role, policy_groups=user.policy_groups or []
        ),
        expires_in=s.jwt_access_token_ttl_minutes * 60,
    )


@router.get("/me", response_model=MeResponse)
def me(user: AuthenticatedUser = Depends(get_current_user)) -> MeResponse:
    """현재 토큰의 사용자 정보 조회 — UI 가 권한별 화면 분기에 사용."""
    return MeResponse(
        user_id=user.user_id,
        username=user.username,
        role=user.role,
        policy_groups=user.policy_groups,
    )


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    payload: PasswordChangeRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """본인 비밀번호 변경. bootstrap admin 첫 로그인 직후 사용."""
    db_user = db.query(UserModel).filter(UserModel.id == user.user_id).first()
    if not db_user or not verify_password(payload.current_password, db_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_current_password",
        )
    db_user.hashed_password = hash_password(payload.new_password)
    db_user.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    return  # 204 No Content
