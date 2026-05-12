"""정책 버전 관리 API (Phase 3-A).

PRD §X: 정책 변경 시 이전 버전을 보존해 사후 감사/롤백 가능.

엔드포인트:
- GET    /v1/policy-compiler/{policy_id}/versions               이력 조회
- POST   /v1/policy-compiler/{policy_id}/versions               새 버전 등록 (YAML 스냅샷 첨부)
- PUT    /v1/policy-compiler/{policy_id}/versions/{ver}/activate 특정 버전 활성화 (롤백 포함)
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.core.dependencies import get_db
from src.database.models import PolicyModel, PolicyVersionModel
from src.utils.policy_cache import get_policy_cache

router = APIRouter(prefix="/v1/policy-compiler", tags=["policy-versions"])


# ──────────────────────────────────────────────────────────────
# Schemas
# ──────────────────────────────────────────────────────────────


class PolicyVersionItem(BaseModel):
    id: str
    policy_id: str
    version: str
    yaml_path: str
    is_current: bool
    created_at: datetime
    activated_at: datetime | None
    deactivated_at: datetime | None


class PolicyVersionListResponse(BaseModel):
    items: list[PolicyVersionItem]
    total: int


class PolicyVersionCreate(BaseModel):
    version: str = Field(min_length=1, max_length=50)
    yaml_path: str = Field(min_length=1, max_length=512)
    yaml_snapshot: str | None = None
    activate: bool = False  # True 면 즉시 활성화 (기존 버전 자동 비활성화)


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────


def _ensure_policy(db: Session, policy_id: str) -> PolicyModel:
    p = db.query(PolicyModel).filter(PolicyModel.id == policy_id).first()
    if not p:
        raise HTTPException(status_code=404, detail=f"policy_id={policy_id} 없음")
    return p


def _to_item(row: PolicyVersionModel) -> PolicyVersionItem:
    return PolicyVersionItem(
        id=row.id,
        policy_id=row.policy_id,
        version=row.version,
        yaml_path=row.yaml_path,
        is_current=row.is_current,
        created_at=row.created_at,
        activated_at=row.activated_at,
        deactivated_at=row.deactivated_at,
    )


def _deactivate_current(db: Session, policy_id: str, now: datetime) -> None:
    """주어진 policy_id 의 현재 활성 버전을 비활성화. is_current=TRUE 행은 최대 1개."""
    current_rows = db.query(PolicyVersionModel).filter(
        PolicyVersionModel.policy_id == policy_id,
        PolicyVersionModel.is_current == True,
    ).all()
    for current in current_rows:
        current.is_current = False
        current.deactivated_at = now


# ──────────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────────


@router.get("/{policy_id}/versions", response_model=PolicyVersionListResponse)
def list_versions(
    policy_id: str, db: Session = Depends(get_db)
) -> PolicyVersionListResponse:
    _ensure_policy(db, policy_id)
    rows = (
        db.query(PolicyVersionModel)
        .filter(PolicyVersionModel.policy_id == policy_id)
        .order_by(PolicyVersionModel.created_at.desc())
        .all()
    )
    return PolicyVersionListResponse(
        items=[_to_item(r) for r in rows],
        total=len(rows),
    )


@router.post(
    "/{policy_id}/versions", response_model=PolicyVersionItem, status_code=201
)
def create_version(
    policy_id: str,
    payload: PolicyVersionCreate,
    db: Session = Depends(get_db),
) -> PolicyVersionItem:
    """새 버전 row INSERT. version 은 (policy_id, version) 유니크.

    activate=True 면 기존 활성 버전 비활성화 후 신규를 활성화.
    """
    _ensure_policy(db, policy_id)

    dup = db.query(PolicyVersionModel).filter(
        PolicyVersionModel.policy_id == policy_id,
        PolicyVersionModel.version == payload.version,
    ).first()
    if dup:
        raise HTTPException(
            status_code=409,
            detail=f"버전 중복: policy_id={policy_id}, version={payload.version}",
        )

    now = datetime.now(timezone.utc)
    if payload.activate:
        _deactivate_current(db, policy_id, now)

    row = PolicyVersionModel(
        id=str(uuid4()),
        policy_id=policy_id,
        version=payload.version,
        yaml_path=payload.yaml_path,
        yaml_snapshot=payload.yaml_snapshot,
        is_current=payload.activate,
        activated_at=now if payload.activate else None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    # Phase 3-B: activate=True 면 다음 요청부터 새 버전이 적용되도록 캐시 무효화
    if payload.activate:
        get_policy_cache().invalidate(policy_id)

    return _to_item(row)


@router.put(
    "/{policy_id}/versions/{version}/activate", response_model=PolicyVersionItem
)
def activate_version(
    policy_id: str,
    version: str,
    db: Session = Depends(get_db),
) -> PolicyVersionItem:
    """특정 버전을 활성화 (롤백 포함). 기존 활성 버전은 자동 비활성화."""
    _ensure_policy(db, policy_id)
    target = db.query(PolicyVersionModel).filter(
        PolicyVersionModel.policy_id == policy_id,
        PolicyVersionModel.version == version,
    ).first()
    if not target:
        raise HTTPException(
            status_code=404,
            detail=f"version={version} 없음 (policy_id={policy_id})",
        )

    now = datetime.now(timezone.utc)
    if target.is_current:
        # idempotent — 이미 활성이면 그대로 반환
        return _to_item(target)

    _deactivate_current(db, policy_id, now)
    target.is_current = True
    target.activated_at = now
    target.deactivated_at = None
    db.commit()
    db.refresh(target)

    # Phase 3-B: 활성 버전이 바뀌었으므로 해당 정책의 캐시 엔트리 모두 무효화
    get_policy_cache().invalidate(policy_id)

    return _to_item(target)
