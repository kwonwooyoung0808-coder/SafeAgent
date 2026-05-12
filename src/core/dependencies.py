from collections.abc import Generator
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from src.core.auth import TokenError, decode_token, hash_api_key
from src.database.connection import SessionLocal
from src.database.models import ApiKeyModel, UserModel


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ──────────────────────────────────────────────────────────────
# Phase 4: 인증 의존성
# ──────────────────────────────────────────────────────────────


class AuthenticatedUser:
    """JWT 검증을 통과한 사용자. 라우터에서 role 기반 분기에 사용."""

    __slots__ = ("user_id", "username", "role", "policy_groups")

    def __init__(self, *, user_id: str, username: str, role: str, policy_groups: list):
        self.user_id = user_id
        self.username = username
        self.role = role
        self.policy_groups = policy_groups


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> AuthenticatedUser:
    """Authorization: Bearer <jwt> 헤더에서 access token 검증 후 사용자 반환.

    토큰 만료/서명 오류 → 401. 비활성/삭제 사용자 → 401.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing_bearer_token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = decode_token(token, expected_type="access")
    except TokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(UserModel).filter(UserModel.id == payload["sub"]).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="user_inactive_or_deleted",
        )
    return AuthenticatedUser(
        user_id=user.id,
        username=user.username,
        role=user.role,
        policy_groups=user.policy_groups or [],
    )


def require_role(*allowed_roles: str):
    """라우터에 첨부할 role 가드. 사용 예:

        @router.post("/...", dependencies=[Depends(require_role("admin"))])

    FastAPI 가 sub-dependency `get_current_user` 를 callable identity 기준으로
    캐시하므로 한 요청 내 DB 조회는 1회로 dedup 됨.
    """
    allowed = set(allowed_roles)

    def _checker(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
        if user.role not in allowed:
            # 보안: role 값을 응답에 노출하지 않음 (정보 누출 방지).
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="forbidden",
            )
        return user

    return _checker


# ──────────────────────────────────────────────────────────────
# API Key (머신 — Sovereign AI Agent)
# ──────────────────────────────────────────────────────────────


def require_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    db: Session = Depends(get_db),
) -> ApiKeyModel:
    """X-API-Key 헤더 검증 후 ApiKeyModel 반환. last_used_at 갱신.

    검증 흐름:
      1) 헤더 raw 키를 SHA-256 해시
      2) DB 의 unique 인덱스에서 해당 해시 검색 — 일치 시 그 row 가 정답
         (256비트 엔트로피 + B-tree 인덱스 lookup → 실질 timing leak 없음)
      3) is_active / expires_at 검증
    """
    if not x_api_key or not x_api_key.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing_api_key",
        )
    raw = x_api_key.strip()
    candidate_hash = hash_api_key(raw)

    api_key = db.query(ApiKeyModel).filter(ApiKeyModel.key_hash == candidate_hash).first()
    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_api_key",
        )
    if not api_key.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="api_key_disabled")
    if (
        api_key.expires_at is not None
        and api_key.expires_at < datetime.now(timezone.utc).replace(tzinfo=None)
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="api_key_expired")

    # 마지막 사용 시각 갱신 (best-effort, 실패해도 인증은 통과)
    try:
        api_key.last_used_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()
    except Exception:
        db.rollback()
    return api_key


def get_trace_id(x_trace_id: str | None = Header(default=None)) -> str:
    """PRD §6 trace_id 체인.

    클라이언트가 X-Trace-Id 헤더를 주면 그 값을 그대로 사용,
    없으면 서버에서 새 UUID 발급.

    같은 사용자 요청이 F1 → SovereignAI → F2 → audit → violation_report
    까지 흐르는 동안 동일 trace_id 가 유지되어 사후 추적이 가능하다.
    """
    if x_trace_id and x_trace_id.strip():
        return x_trace_id.strip()[:80]  # 컬럼 길이 보호
    return str(uuid4())

