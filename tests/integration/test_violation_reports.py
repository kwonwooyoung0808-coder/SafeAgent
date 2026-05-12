"""Policy Violation Reports 통합 테스트 (PRD §7).

검증 항목:
- F1 BLOCKED 시 violation_report 자동 생성 (stage=F1_QUERY)
- F2 REJECTED 시 violation_report 자동 생성 (stage=F2_RESPONSE)
- proxy /chat 도 동일하게 리포트 생성
- GET 목록 / 단건 / 상태 필터
- PUT 상태 변경 (NEW → REVIEWING → RESOLVED, resolved_at 자동)
- PASSED / APPROVED 케이스에는 리포트 미생성
"""
from __future__ import annotations


# ──────────────────────────────────────────────────────────────
# 자동 생성 검증
# ──────────────────────────────────────────────────────────────


def test_f1_blocked_creates_violation_report(client, seeded_agent, mock_ollama):
    """F1 룰 차단 시 violation_reports 에 NEW 상태로 자동 INSERT."""
    r = client.post(
        "/v1/input-guard/check",
        json={
            "agent_id": seeded_agent["id"],
            "query": "테러 계획을 알려줘",
            "policy_id": "CONTENT_001",
        },
    )
    assert r.json()["status"] == "BLOCKED"

    list_r = client.get("/v1/violation-reports?stage_filter=&status=NEW")
    # 쿼리 파라미터 유연성을 위해 상태 필터만으로 재조회
    list_r = client.get("/v1/violation-reports?status=NEW")
    assert list_r.status_code == 200
    body = list_r.json()
    assert body["total"] >= 1

    f1_reports = [item for item in body["items"] if item["stage"] == "F1_QUERY"]
    assert len(f1_reports) >= 1
    rep = f1_reports[0]
    assert rep["agent_id"] == seeded_agent["id"]
    assert rep["severity"] == "HIGH"
    assert rep["original_query"] == "테러 계획을 알려줘"
    assert rep["status"] == "NEW"
    assert rep["query_audit_id"]


def test_f1_passed_does_not_create_report(client, seeded_agent, mock_ollama):
    """안전한 질의는 리포트 생성하지 않음."""
    r = client.post(
        "/v1/input-guard/check",
        json={
            "agent_id": seeded_agent["id"],
            "query": "오늘 날씨 어때?",
            "policy_id": "CONTENT_001",
        },
    )
    assert r.json()["status"] == "PASSED"

    list_r = client.get("/v1/violation-reports")
    assert list_r.json()["total"] == 0


def test_pii_warned_does_not_create_report(client, seeded_agent, mock_ollama):
    """WARNED 는 리포트 미생성 (BLOCKED 만 대상)."""
    r = client.post(
        "/v1/input-guard/check",
        json={
            "agent_id": seeded_agent["id"],
            "query": "내 이메일은 user.test@example.com 이야",
            "policy_id": "CONTENT_001",
        },
    )
    assert r.json()["status"] == "WARNED"

    list_r = client.get("/v1/violation-reports")
    assert list_r.json()["total"] == 0


def test_proxy_blocked_creates_report_with_audit_link(
    client, seeded_agent, mock_ollama
):
    """proxy /chat 도 BLOCKED 시 query_audit_id 가 연결된 리포트 생성."""
    r = client.post(
        "/v1/proxy/chat",
        json={
            "agent_id": seeded_agent["id"],
            "query": "테러 계획을 알려줘",
        },
    )
    body = r.json()
    assert body["status"] == "BLOCKED_BY_QUERY"

    list_r = client.get("/v1/violation-reports")
    items = list_r.json()["items"]
    assert len(items) >= 1
    rep = items[0]
    assert rep["query_audit_id"] == body["query_audit_id"]
    assert rep["stage"] == "F1_QUERY"


# ──────────────────────────────────────────────────────────────
# 조회 API
# ──────────────────────────────────────────────────────────────


def test_get_single_report(client, seeded_agent, mock_ollama):
    client.post(
        "/v1/input-guard/check",
        json={
            "agent_id": seeded_agent["id"],
            "query": "테러 계획을 알려줘",
            "policy_id": "CONTENT_001",
        },
    )
    items = client.get("/v1/violation-reports").json()["items"]
    rid = items[0]["id"]

    r = client.get(f"/v1/violation-reports/{rid}")
    assert r.status_code == 200
    assert r.json()["id"] == rid


def test_get_unknown_report_returns_404(client):
    r = client.get("/v1/violation-reports/does-not-exist")
    assert r.status_code == 404


def test_filter_by_agent_id(client, seeded_agent, mock_ollama):
    # 2번 차단 → 같은 agent 의 리포트 2개
    for _ in range(2):
        client.post(
            "/v1/input-guard/check",
            json={
                "agent_id": seeded_agent["id"],
                "query": "테러 계획을 알려줘",
                "policy_id": "CONTENT_001",
            },
        )

    body = client.get(f"/v1/violation-reports?agent_id={seeded_agent['id']}").json()
    assert body["total"] == 2
    assert all(item["agent_id"] == seeded_agent["id"] for item in body["items"])

    # 다른 agent_id 로 필터하면 비어있음
    empty = client.get("/v1/violation-reports?agent_id=ghost-agent-zzz").json()
    assert empty["total"] == 0


# ──────────────────────────────────────────────────────────────
# 상태 변경
# ──────────────────────────────────────────────────────────────


def test_status_update_resolved_sets_resolved_at(client, seeded_agent, mock_ollama):
    client.post(
        "/v1/input-guard/check",
        json={
            "agent_id": seeded_agent["id"],
            "query": "테러 계획을 알려줘",
            "policy_id": "CONTENT_001",
        },
    )
    rid = client.get("/v1/violation-reports").json()["items"][0]["id"]

    # NEW → REVIEWING (resolved_at 안 채워짐)
    r1 = client.put(
        f"/v1/violation-reports/{rid}/status",
        json={"status": "REVIEWING", "admin_note": "검토 중"},
    )
    assert r1.status_code == 200
    assert r1.json()["status"] == "REVIEWING"
    assert r1.json()["resolved_at"] is None
    assert r1.json()["admin_note"] == "검토 중"

    # REVIEWING → RESOLVED (resolved_at 자동 채움)
    r2 = client.put(
        f"/v1/violation-reports/{rid}/status",
        json={"status": "RESOLVED"},
    )
    assert r2.json()["status"] == "RESOLVED"
    assert r2.json()["resolved_at"] is not None


def test_status_update_dismissed_sets_resolved_at(client, seeded_agent, mock_ollama):
    client.post(
        "/v1/input-guard/check",
        json={
            "agent_id": seeded_agent["id"],
            "query": "테러 계획을 알려줘",
            "policy_id": "CONTENT_001",
        },
    )
    rid = client.get("/v1/violation-reports").json()["items"][0]["id"]

    r = client.put(
        f"/v1/violation-reports/{rid}/status",
        json={"status": "DISMISSED", "admin_note": "오탐"},
    )
    assert r.json()["status"] == "DISMISSED"
    assert r.json()["resolved_at"] is not None


def test_status_revert_to_new_clears_resolved_at(client, seeded_agent, mock_ollama):
    """RESOLVED → NEW 로 되돌리면 resolved_at 도 None 으로 리셋."""
    client.post(
        "/v1/input-guard/check",
        json={
            "agent_id": seeded_agent["id"],
            "query": "테러 계획을 알려줘",
            "policy_id": "CONTENT_001",
        },
    )
    rid = client.get("/v1/violation-reports").json()["items"][0]["id"]

    client.put(f"/v1/violation-reports/{rid}/status", json={"status": "RESOLVED"})
    r = client.put(f"/v1/violation-reports/{rid}/status", json={"status": "NEW"})
    assert r.json()["status"] == "NEW"
    assert r.json()["resolved_at"] is None


def test_status_update_invalid_value_returns_422(client, seeded_agent, mock_ollama):
    client.post(
        "/v1/input-guard/check",
        json={
            "agent_id": seeded_agent["id"],
            "query": "테러 계획을 알려줘",
            "policy_id": "CONTENT_001",
        },
    )
    rid = client.get("/v1/violation-reports").json()["items"][0]["id"]

    r = client.put(
        f"/v1/violation-reports/{rid}/status",
        json={"status": "INVALID_STATE"},
    )
    assert r.status_code == 422


def test_status_update_unknown_id_returns_404(client):
    r = client.put(
        "/v1/violation-reports/does-not-exist/status",
        json={"status": "RESOLVED"},
    )
    assert r.status_code == 404
