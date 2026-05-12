"""P1 운영 모니터링 엔드포인트 통합 테스트.

검증 항목:
- /health/cache : 캐시 통계 (size, hits, misses, hit_ratio)
- /health/system: DB + 엔터티 카운트
- /health/llm  : Sovereign / Governance LLM ping (네트워크 의존 — 도달 실패도 200)
"""
from __future__ import annotations

import pytest


# ──────────────────────────────────────────────────────────────
# /health/cache
# ──────────────────────────────────────────────────────────────


def test_cache_health_returns_stats(client):
    r = client.get("/health/cache")
    assert r.status_code == 200
    body = r.json()
    assert set(body.keys()) == {
        "size", "hits", "misses", "total_requests", "hit_ratio",
    }
    # 빈 캐시는 hit_ratio = 0
    assert isinstance(body["size"], int)
    assert isinstance(body["hit_ratio"], float)


def test_cache_health_reflects_workflow_calls(
    client, seeded_agent, mock_ollama
):
    """워크플로우 실행 후 캐시에 적재되어 size > 0 이어야 함."""
    # 캐시 초기화 (다른 테스트의 영향 차단)
    from src.utils.policy_cache import get_policy_cache
    get_policy_cache().clear()

    client.post(
        "/v1/input-guard/check",
        json={
            "agent_id": seeded_agent["id"],
            "query": "안녕하세요",
            "policy_id": "CONTENT_001",
        },
    )

    body = client.get("/health/cache").json()
    assert body["size"] >= 1
    assert body["misses"] >= 1


# ──────────────────────────────────────────────────────────────
# /health/system
# ──────────────────────────────────────────────────────────────


def test_system_health_reports_counts(client, seeded_agent):
    r = client.get("/health/system")
    assert r.status_code == 200
    body = r.json()
    assert body["db_available"] is True
    assert "counts" in body
    counts = body["counts"]
    # 시드된 정책 + 등록된 agent 가 카운트에 반영되어야 함
    assert counts["agents"] >= 1
    assert counts["policies"] >= 1
    # 신규 테이블도 빈 카운트로 노출
    assert "policy_groups" in counts
    assert "policy_versions" in counts
    assert "violation_reports" in counts


def test_system_health_succeeds_with_empty_db(client):
    """시드만 있고 agent 없을 때도 200 + 카운트 노출."""
    body = client.get("/health/system").json()
    assert body["db_available"] is True
    assert body["counts"]["agents"] == 0


# ──────────────────────────────────────────────────────────────
# /health/llm
# ──────────────────────────────────────────────────────────────


def test_llm_health_returns_both_clients(client, monkeypatch):
    """Ollama 도달 안 되더라도 200 + reachable=False 반환 (운영 안전)."""
    # Ollama 가 실행 중이지 않다고 가정 — httpx 클라이언트 모킹으로 강제 실패
    import httpx

    class _FakeClient:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def get(self, url):
            raise httpx.ConnectError("simulated unreachable")

    monkeypatch.setattr(httpx, "AsyncClient", _FakeClient)

    r = client.get("/health/llm")
    assert r.status_code == 200
    body = r.json()
    assert body["sovereign_ai"]["reachable"] is False
    assert body["governance_llm"]["reachable"] is False
    assert "ConnectError" in body["sovereign_ai"]["error"]
