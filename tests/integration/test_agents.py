"""PRD 9 Agent Management API 통합 테스트."""
from __future__ import annotations


def test_create_agent_success(client):
    r = client.post(
        "/api/agents",
        json={
            "id": "agent-1",
            "name": "Test Agent",
            "policy_id": "CONTENT_001",
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["id"] == "agent-1"
    assert body["status"] == "ACTIVE"
    assert body["policy_id"] == "CONTENT_001"


def test_create_agent_auto_id_when_omitted(client):
    r = client.post("/api/agents", json={"name": "AutoId"})
    assert r.status_code == 201
    body = r.json()
    assert body["id"].startswith("agent-")
    assert len(body["id"]) > len("agent-")  # uuid suffix 존재


def test_create_agent_duplicate_id_returns_409(client):
    payload = {"id": "agent-dup", "name": "Dup", "policy_id": "CONTENT_001"}
    r1 = client.post("/api/agents", json=payload)
    assert r1.status_code == 201
    r2 = client.post("/api/agents", json=payload)
    assert r2.status_code == 409


def test_create_agent_with_invalid_policy_returns_422(client):
    r = client.post(
        "/api/agents",
        json={"id": "agent-bad", "name": "Bad", "policy_id": "DOES_NOT_EXIST"},
    )
    assert r.status_code == 422


def test_get_agent_not_found_returns_404(client):
    r = client.get("/api/agents/missing")
    assert r.status_code == 404


def test_get_agent_returns_created_data(client, seeded_agent):
    r = client.get(f"/api/agents/{seeded_agent['id']}")
    assert r.status_code == 200
    assert r.json()["name"] == "Test Agent"


def test_update_agent_policy_success(client, seeded_agent):
    # CONTENT_001 → CONTENT_002로 변경
    r = client.put(
        f"/api/agents/{seeded_agent['id']}/policy",
        json={"policy_id": "CONTENT_002"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["policy_id"] == "CONTENT_002"


def test_update_agent_policy_invalid_returns_422(client, seeded_agent):
    r = client.put(
        f"/api/agents/{seeded_agent['id']}/policy",
        json={"policy_id": "NOT_REAL"},
    )
    assert r.status_code == 422


def test_get_agent_audit_empty_initially(client, seeded_agent):
    r = client.get(f"/api/agents/{seeded_agent['id']}/audit")
    assert r.status_code == 200
    body = r.json()
    assert body["agent_id"] == seeded_agent["id"]
    assert body["query_audits"] == []
    assert body["response_audits"] == []
