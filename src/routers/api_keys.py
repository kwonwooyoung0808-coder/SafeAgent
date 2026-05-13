"""Phase 4: API Key 관리 — Sovereign AI Agent (머신) 인증용.

발급된 평문 키는 응답에 1회만 노출 (DB 엔 SHA-256 해시만 보관).
재조회 불가 — 분실 시 재발급.

Phase 5 예정 보강 (현재 미구현):
  - BOLA — multi-tenant 도입 시 owner_user_id 검증 (현재는 single-tenant 가정).
"""
from __future__ import annotations

import logging
import uuid as _uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from src.core.auth import generate_api_key
from src.core.dependencies import AuthenticatedUser, get_db, require_role
from src.database.models import AgentModel, ApiKeyModel

router = APIRouter(prefix="/api/agents", tags=["agents"])
logger = logging.getLogger(__name__)


def _to_utc_naive(dt: datetime | None) -> datetime | None:
    """aware datetime → UTC 변환 후 naive 저장. naive 는 UTC 로 가정.

    프로젝트 전체가 naive UTC 컬럼을 쓰므로 KST 등 다른 tz 입력 시 UTC 로 정규화.
    """
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


class ApiKeyCreateRequest(BaseModel):
    description: str | None = Field(default=None, max_length=255)
    expires_at: datetime | None = None

    @field_validator("expires_at")
    @classmethod
    def _must_be_future(cls, v: datetime | None) -> datetime | None:
        if v is None:
            return v
        # 비교 기준: 입력이 aware 면 aware now, 아니면 naive UTC now.
        now = datetime.now(timezone.utc) if v.tzinfo is not None else datetime.now(timezone.utc).replace(tzinfo=None)
        if v <= now:
            raise ValueError("expires_at_must_be_future")
        return v


class ApiKeyCreatedResponse(BaseModel):
    id: str
    agent_id: str
    api_key: str  # 평문 — 1회만 노출
    description: str | None
    expires_at: datetime | None
    created_at: datetime


class ApiKeyListItem(BaseModel):
    id: str
    description: str | None
    is_active: bool
    expires_at: datetime | None
    last_used_at: datetime | None
    created_at: datetime


@router.post(
    "/{agent_id}/api-keys",
    response_model=ApiKeyCreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_api_key(
    agent_id: str,
    payload: ApiKeyCreateRequest,
    user: AuthenticatedUser = Depends(require_role("admin", "operator")),
    db: Session = Depends(get_db),
) -> ApiKeyCreatedResponse:
    """Agent 에 새 API Key 발급. 평문은 응답에 1회만 노출."""
    if not db.query(AgentModel).filter(AgentModel.id == agent_id).first():
        raise HTTPException(status_code=404, detail="agent_not_found")

    raw, hashed = generate_api_key()
    record = ApiKeyModel(
        id=f"apikey-{_uuid.uuid4()}",
        agent_id=agent_id,
        key_hash=hashed,
        description=payload.description,
        is_active=True,
        expires_at=_to_utc_naive(payload.expires_at),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    # ISMS-P 2.11: 보안 이벤트 감사 로그.
    logger.info(
        "[AUDIT] api_key_issued key_id=%s agent_id=%s issued_by=%s expires_at=%s",
        record.id, agent_id, user.user_id, record.expires_at,
    )
    return ApiKeyCreatedResponse(
        id=record.id,
        agent_id=record.agent_id,
        api_key=raw,
        description=record.description,
        expires_at=record.expires_at,
        created_at=record.created_at,
    )


@router.get("/{agent_id}/api-keys", response_model=list[ApiKeyListItem])
def list_api_keys(
    agent_id: str,
    user: AuthenticatedUser = Depends(require_role("admin", "operator", "viewer")),
    db: Session = Depends(get_db),
) -> list[ApiKeyListItem]:
    """Agent 의 API Key 목록 — 평문/해시 노출 없음, 메타데이터만."""
    if not db.query(AgentModel).filter(AgentModel.id == agent_id).first():
        raise HTTPException(status_code=404, detail="agent_not_found")

    rows = (
        db.query(ApiKeyModel)
        .filter(ApiKeyModel.agent_id == agent_id)
        .order_by(ApiKeyModel.created_at.desc())
        .all()
    )
    return [
        ApiKeyListItem(
            id=r.id,
            description=r.description,
            is_active=r.is_active,
            expires_at=r.expires_at,
            last_used_at=r.last_used_at,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.delete(
    "/{agent_id}/api-keys/{key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def revoke_api_key(
    agent_id: str,
    key_id: str,
    user: AuthenticatedUser = Depends(require_role("admin", "operator")),
    db: Session = Depends(get_db),
):
    """API Key 비활성화 (soft revoke — 행은 보존, is_active=False).

    REST 모범사례 — DELETE 는 idempotent. 이미 폐기된 키에 다시 호출해도 204.
    """
    record = (
        db.query(ApiKeyModel)
        .filter(ApiKeyModel.id == key_id, ApiKeyModel.agent_id == agent_id)
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail="api_key_not_found")
    if record.is_active:
        record.is_active = False
        db.commit()
        logger.info(
            "[AUDIT] api_key_revoked key_id=%s agent_id=%s revoked_by=%s",
            key_id, agent_id, user.user_id,
        )
    return
