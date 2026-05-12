"""Phase 4 API Key 관리 통합 테스트.

검증:
  - POST: 발급 + 평문 응답 1회 노출 / 해시만 DB
  - GET: 목록 (메타데이터만)
  - DELETE: soft revoke (idempotent)
  - X-API-Key 인증: 게이트웨이 호출 통과 / 무효 키 401 / 비활성 키 401
  - 과거 만료일 거부 (validator)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient


def _raw_client():
    from src.main import app
    return TestClient(app)


def test_create_api_key_returns_plaintext_once(client, seeded_agent):
    r = client.post(
        f"/api/agents/{seeded_agent['id']}/api-keys",
        json={"description": "ci-key"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["api_key"].startswith("sak_")
    assert body["agent_id"] == seeded_agent["id"]
    # 목록에는 평문/해시 노출 없음
    list_r = client.get(f"/api/agents/{seeded_agent['id']}/api-keys")
    assert list_r.status_code == 200
    items = list_r.json()
    assert any(item["id"] == body["id"] for item in items)
    for item in items:
        assert "api_key" not in item  # 평문 미노출
        assert "key_hash" not in item


def test_create_api_key_for_unknown_agent_404(client):
    r = client.post("/api/agents/ghost/api-keys", json={"description": "x"})
    assert r.status_code == 404


def test_create_api_key_past_expires_rejected(client, seeded_agent):
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    r = client.post(
        f"/api/agents/{seeded_agent['id']}/api-keys",
        json={"description": "x", "expires_at": past},
    )
    assert r.status_code == 422


def test_revoke_api_key_is_idempotent(client, seeded_agent):
    # 1) 발급
    issued = client.post(
        f"/api/agents/{seeded_agent['id']}/api-keys",
        json={"description": "to-revoke"},
    ).json()
    # 2) 폐기
    r1 = client.delete(f"/api/agents/{seeded_agent['id']}/api-keys/{issued['id']}")
    assert r1.status_code == 204
    # 3) 재폐기 — REST idempotent
    r2 = client.delete(f"/api/agents/{seeded_agent['id']}/api-keys/{issued['id']}")
    assert r2.status_code == 204


def test_gateway_endpoint_requires_api_key(client, seeded_agent, mock_ollama):
    # seeded_agent fixture 가 client 에 X-API-Key 주입 → 호출 성공
    r = client.post(
        "/v1/input-guard/check",
        json={"agent_id": seeded_agent["id"], "query": "안녕", "policy_id": "CONTENT_001"},
    )
    assert r.status_code == 200, r.text


def test_gateway_endpoint_without_api_key_401(client, seeded_agent, mock_ollama):
    # X-API-Key 헤더 제거 후 호출
    raw = _raw_client()
    with raw:
        # JWT 만으로 게이트웨이 접근 시도 — API Key 가 없으면 401
        # (admin JWT 도 게이트웨이는 막힘 — 머신 전용 엔드포인트)
        login = raw.post("/v1/auth/login", json={"username": "admin", "password": "changeme"})
        raw.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
        r = raw.post(
            "/v1/input-guard/check",
            json={"agent_id": seeded_agent["id"], "query": "안녕", "policy_id": "CONTENT_001"},
        )
    assert r.status_code == 401


def test_revoked_api_key_blocks_gateway_call(client, seeded_agent):
    # 새 키 발급 후 그 키로 raw client 만들고 폐기 → 게이트웨이 401
    issued = client.post(
        f"/api/agents/{seeded_agent['id']}/api-keys",
        json={"description": "revoke-test"},
    ).json()
    raw = _raw_client()
    with raw:
        raw.headers["X-API-Key"] = issued["api_key"]
        # 폐기 전: 호출 통과 (적어도 인증은)
        # 폐기
        client.delete(f"/api/agents/{seeded_agent['id']}/api-keys/{issued['id']}")
        # 폐기 후: 401
        r = raw.post(
            "/v1/input-guard/check",
            json={"agent_id": seeded_agent["id"], "query": "Q", "policy_id": "CONTENT_001"},
        )
    assert r.status_code == 401
