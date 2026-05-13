from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import logging

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.core.config import _validate_auth_settings, get_settings
from src.core.dependencies import require_api_key, require_role
from src.database.connection import init_db
from src.services.sovereign_ai_client import _validate_sovereign_url
from src.routers import (
    agents,
    api_keys,
    audit,
    auth,
    evaluate,
    health,
    input_guard,
    inquiry,
    policy_compiler,
    policy_groups,
    policy_versions,
    proxy,
    response_guard,
    runs,
    updates,
    violation_reports,
    violations,
)

settings = get_settings()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # 데이터 주권 가드 (fail-fast): SOVEREIGN_AI_URL 이 사내 허용 호스트가 아니면
    # 앱 시작 자체를 거부 — 첫 요청 기다리지 않고 즉시 운영자에게 알림.
    _validate_sovereign_url(settings.sovereign_ai_url)
    # 인증 설정 검증 (RFC 7518 §3.2 JWT_SECRET 32B+ / 운영 환경 약한 admin pw 차단)
    _validate_auth_settings(settings)
    if settings.demo_auth_bypass:
        logger.warning(
            "[SECURITY] DEMO_AUTH_BYPASS is enabled. JWT/API Key checks are bypassed "
            "for local demo only; production startup rejects this setting."
        )

    app.state.db_available = init_db()
    yield


openapi_tags = [
    {"name": "health", "description": "운영 모니터링 — 헬스체크 (공개)."},
    {"name": "auth", "description": "Phase 4 인증 — login/refresh/me/password."},
    {"name": "input-guard", "description": "게이트웨이: 입력 검사 (Sovereign AI Agent → API Key 인증)."},
    {"name": "response-guard", "description": "게이트웨이: 응답 검사 (Sovereign AI Agent → API Key 인증)."},
    {"name": "proxy", "description": "게이트웨이: chat proxy (Sovereign AI Agent → API Key 인증)."},
    {"name": "policy-compiler", "description": "정책 라이프사이클 — 컴파일 → draft 검토/수정 → activate → version 관리. 같은 tag로 정책 버전 API도 함께 표시됩니다."},
    {"name": "policy-groups", "description": "정책 그룹 CRUD + 멤버 관리. summary가 운영자 대시보드 진입점입니다."},
    {"name": "agents", "description": "Sovereign AI Agent 등록/조회/정책 그룹 연결 + API Key 발급/관리(같은 tag로 통합)."},
    {"name": "runs", "description": "워크플로 실행 기록 조회."},
    {"name": "violations", "description": "위반 이벤트 조회/요약."},
    {"name": "violation-reports", "description": "위반 보고서."},
    {"name": "audit", "description": "쿼리/응답 감사 로그."},
    {"name": "inquiry", "description": "운영 문의 처리."},
    {"name": "updates", "description": "정책/시스템 업데이트 알림."},
    {"name": "evaluate", "description": "[레거시] 평가 도구 — 관리자 전용."},
]

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
    openapi_tags=openapi_tags,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Phase 4 인증 적용 패턴:
#   - 공개: /health, /v1/auth/login, /v1/auth/refresh
#   - API Key (머신): /v1/input-guard, /v1/response-guard, /v1/proxy
#   - JWT (관리 도구): /api/v1/evaluate 및 관리/조회 API
#   - JWT (사람, 모든 role): 그 외 관리/조회 API
#   - 세분화 role: api_keys.router 는 per-endpoint 적용 / 정책 활성화 admin-only 는 Phase 5
_jwt_any = [Depends(require_role("admin", "operator", "viewer"))]
_machine = [Depends(require_api_key)]

# 운영 모니터링 (공개 — 헬스체크는 인증 없이 도달 가능해야 함)
app.include_router(health.router)

# Phase 4: 인증 (login/refresh 는 자체 공개, me/password 는 내부적으로 토큰 검증)
app.include_router(auth.router)

# 게이트웨이 흐름 — Sovereign AI Agent (머신) 가 호출. API Key 인증.
app.include_router(input_guard.router, dependencies=_machine)
app.include_router(response_guard.router, dependencies=_machine)
app.include_router(proxy.router, dependencies=_machine)
app.include_router(evaluate.router, dependencies=_jwt_any)  # 레거시 평가 도구 (관리자용)

# 관리 / 조회 API — JWT 필요 (모든 role 허용, 세분화는 Phase 5)
# 정책 라이프사이클: compiler → versions (같은 tag=policy-compiler 로 묶여 표시됨)
app.include_router(policy_compiler.router, dependencies=_jwt_any)
app.include_router(policy_versions.router, dependencies=_jwt_any)
app.include_router(policy_groups.router, dependencies=_jwt_any)

# Agent 관리: agents → api_keys (같은 tag=agents 로 묶여 표시됨)
app.include_router(agents.router, dependencies=_jwt_any)
# api_keys.router 는 per-endpoint role 체크가 이미 적용됨.
app.include_router(api_keys.router)

# 감사 / 운영 조회
app.include_router(runs.router, dependencies=_jwt_any)
app.include_router(violations.router, dependencies=_jwt_any)
app.include_router(violation_reports.router, dependencies=_jwt_any)
app.include_router(audit.router, dependencies=_jwt_any)
app.include_router(audit.query_audit_router, dependencies=_jwt_any)
app.include_router(inquiry.router, dependencies=_jwt_any)
app.include_router(updates.router, dependencies=_jwt_any)
