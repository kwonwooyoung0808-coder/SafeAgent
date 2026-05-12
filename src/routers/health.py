"""운영 모니터링 엔드포인트 (P1 Phase).

읽기 전용 + 빠른 응답 + 실패 안전.
LLM 실제 추론은 호출하지 않고, 도달 가능성만 ping.
"""
from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.core.config import get_settings
from src.core.dependencies import get_db
from src.database.models import (
    AgentModel,
    PolicyGroupModel,
    PolicyModel,
    PolicyVersionModel,
    QueryAuditLogModel,
    ResponseAuditLogModel,
    ViolationReportModel,
)
from src.utils.policy_cache import get_policy_cache

router = APIRouter(tags=["health"])


# ──────────────────────────────────────────────────────────────
# GET /health — 기본 (기존 유지)
# ──────────────────────────────────────────────────────────────


@router.get("/health")
def health_basic(request: Request) -> dict:
    return {
        "status": "ok",
        "db_available": getattr(request.app.state, "db_available", False),
    }


# ──────────────────────────────────────────────────────────────
# GET /health/cache — 정책 캐시 통계
# ──────────────────────────────────────────────────────────────


@router.get("/health/cache")
def health_cache() -> dict:
    """PolicyCache 의 hit/miss 비율 노출. 운영자 모니터링용."""
    stats = get_policy_cache().stats()
    total = stats["hits"] + stats["misses"]
    hit_ratio = stats["hits"] / total if total > 0 else 0.0
    return {
        "size": stats["size"],
        "hits": stats["hits"],
        "misses": stats["misses"],
        "total_requests": total,
        "hit_ratio": round(hit_ratio, 4),
    }


# ──────────────────────────────────────────────────────────────
# GET /health/system — DB + 엔터티 등록 카운트
# ──────────────────────────────────────────────────────────────


def _safe_count(db: Session, model) -> int | None:
    """DB 에러 시 None 반환 (헬스체크가 DB 다운 때문에 죽지 않도록)."""
    try:
        return db.scalar(select(func.count()).select_from(model))
    except SQLAlchemyError:
        return None


@router.get("/health/system")
def health_system(request: Request, db: Session = Depends(get_db)) -> dict:
    """등록된 엔터티 수 + DB 가용성. 운영 대시보드용."""
    return {
        "db_available": getattr(request.app.state, "db_available", False),
        "counts": {
            "agents": _safe_count(db, AgentModel),
            "policies": _safe_count(db, PolicyModel),
            "policy_versions": _safe_count(db, PolicyVersionModel),
            "policy_groups": _safe_count(db, PolicyGroupModel),
            "query_audit_logs": _safe_count(db, QueryAuditLogModel),
            "response_audit_logs": _safe_count(db, ResponseAuditLogModel),
            "violation_reports": _safe_count(db, ViolationReportModel),
        },
    }


# ──────────────────────────────────────────────────────────────
# GET /health/llm — Ollama / Sovereign AI 도달 가능성
# ──────────────────────────────────────────────────────────────


async def _ping_ollama(url: str) -> dict:
    """Ollama /api/tags 로 도달 가능성 확인. LLM 추론은 안 호출."""
    base = url.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{base}/api/tags")
            if r.status_code == 200:
                models = [m.get("name") for m in r.json().get("models", [])]
                return {"reachable": True, "loaded_models": models}
            return {
                "reachable": False,
                "error": f"HTTP {r.status_code}",
            }
    except Exception as e:
        return {
            "reachable": False,
            "error": f"{type(e).__name__}: {e}" if str(e) else type(e).__name__,
        }


@router.get("/health/llm")
async def health_llm() -> dict:
    """Sovereign AI / Governance LLM 의 ping 결과. 추론 호출 없음."""
    settings = get_settings()
    sovereign = await _ping_ollama(settings.sovereign_ai_url)
    governance = await _ping_ollama(settings.governance_llm_url)
    return {
        "sovereign_ai": {
            "url": settings.sovereign_ai_url,
            "model": settings.sovereign_ai_model,
            **sovereign,
        },
        "governance_llm": {
            "url": settings.governance_llm_url,
            "model": settings.governance_llm_model,
            **governance,
        },
    }
