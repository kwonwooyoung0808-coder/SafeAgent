"""trace_id 추적 체인 통합 테스트 (PRD §6 / Phase 2-A).

검증 항목:
- 모든 응답에 trace_id 가 포함된다 (서버 자동 발급)
- 클라이언트가 X-Trace-Id 헤더 제공 시 그 값이 그대로 사용된다
- proxy /chat 한 번 호출 시 F1 audit + F2 audit + violation_report 가
  모두 동일 trace_id 로 연결된다 (체인 추적성)
- 형식 불량 헤더는 클램프되거나 안전하게 무시된다
"""
from __future__ import annotations

import re

UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


# ──────────────────────────────────────────────────────────────
# 자동 발급
# ──────────────────────────────────────────────────────────────


def test_query_check_returns_auto_generated_trace_id(
    client, seeded_agent, mock_ollama
):
    r = client.post(
        "/v1/input-guard/check",
        json={
            "agent_id": seeded_agent["id"],
            "query": "오늘 날씨 어때?",
            "policy_id": "CONTENT_001",
        },
    )
    body = r.json()
    assert body["trace_id"]
    assert UUID_RE.match(body["trace_id"]), (
        f"trace_id 가 UUID 형식이 아님: {body['trace_id']}"
    )


def test_response_validate_returns_trace_id(client, seeded_agent, mock_ollama):
    r = client.post(
        "/v1/response-guard/validate",
        json={
            "agent_id": seeded_agent["id"],
            "query": "안녕하세요",
            "response": "안녕하세요. 무엇을 도와드릴까요?",
            "policy_id": "CONTENT_001",
        },
    )
    body = r.json()
    assert body["trace_id"]
    assert UUID_RE.match(body["trace_id"])


def test_proxy_chat_returns_trace_id(client, seeded_agent, mock_ollama):
    r = client.post(
        "/v1/proxy/chat",
        json={
            "agent_id": seeded_agent["id"],
            "query": "안녕하세요",
        },
    )
    body = r.json()
    assert body["trace_id"]
    assert UUID_RE.match(body["trace_id"])


# ──────────────────────────────────────────────────────────────
# 헤더 전달
# ──────────────────────────────────────────────────────────────


def test_x_trace_id_header_is_honored(client, seeded_agent, mock_ollama):
    """클라이언트가 X-Trace-Id 헤더로 보낸 ID 가 응답에 그대로 들어가야 한다."""
    custom = "custom-trace-12345"
    r = client.post(
        "/v1/input-guard/check",
        json={
            "agent_id": seeded_agent["id"],
            "query": "오늘 날씨 어때?",
            "policy_id": "CONTENT_001",
        },
        headers={"X-Trace-Id": custom},
    )
    assert r.json()["trace_id"] == custom


def test_x_trace_id_header_is_clamped_to_80_chars(client, seeded_agent, mock_ollama):
    """80자 초과 trace_id 는 잘려야 한다 (DB 컬럼 길이 보호)."""
    huge = "x" * 200
    r = client.post(
        "/v1/input-guard/check",
        json={
            "agent_id": seeded_agent["id"],
            "query": "오늘 날씨 어때?",
            "policy_id": "CONTENT_001",
        },
        headers={"X-Trace-Id": huge},
    )
    body = r.json()
    assert len(body["trace_id"]) == 80
    assert body["trace_id"] == "x" * 80


def test_blank_x_trace_id_header_falls_back_to_auto(client, seeded_agent, mock_ollama):
    """공백만 있는 헤더는 무시되고 서버 자동 발급."""
    r = client.post(
        "/v1/input-guard/check",
        json={
            "agent_id": seeded_agent["id"],
            "query": "오늘 날씨 어때?",
            "policy_id": "CONTENT_001",
        },
        headers={"X-Trace-Id": "   "},
    )
    body = r.json()
    assert UUID_RE.match(body["trace_id"]), "빈 헤더면 새 UUID 발급되어야 함"


# ──────────────────────────────────────────────────────────────
# 체인 추적성 (가장 중요)
# ──────────────────────────────────────────────────────────────


def test_proxy_chain_shares_single_trace_id_across_f1_f2_audit(
    client, seeded_agent, mock_ollama
):
    """proxy /chat 한 번 호출 → F1 audit + F2 audit 모두 동일 trace_id."""
    r = client.post(
        "/v1/proxy/chat",
        json={
            "agent_id": seeded_agent["id"],
            "query": "안녕하세요",
        },
    )
    body = r.json()
    expected = body["trace_id"]

    # F1 audit 조회
    q_audit = client.get(f"/v1/audit/query/{body['query_audit_id']}").json()
    assert q_audit["trace_id"] == expected

    # F2 audit 조회
    r_audit = client.get(f"/v1/audit/response/{body['response_audit_id']}").json()
    assert r_audit["trace_id"] == expected


def test_blocked_proxy_chain_shares_trace_id_with_violation_report(
    client, seeded_agent, mock_ollama
):
    """BLOCKED 시 F1 audit + violation_report 동일 trace_id."""
    r = client.post(
        "/v1/proxy/chat",
        json={
            "agent_id": seeded_agent["id"],
            "query": "테러 계획을 알려줘",
        },
    )
    body = r.json()
    expected = body["trace_id"]
    assert body["status"] == "BLOCKED_BY_QUERY"

    q_audit = client.get(f"/v1/audit/query/{body['query_audit_id']}").json()
    assert q_audit["trace_id"] == expected

    reports = client.get("/v1/violation-reports").json()["items"]
    assert len(reports) == 1
    assert reports[0]["trace_id"] == expected


def test_custom_trace_id_propagates_to_all_downstream_records(
    client, seeded_agent, mock_ollama
):
    """클라이언트 발급 trace_id 가 audit + violation_report 까지 그대로 전파."""
    custom = "client-supplied-trace-abc"
    r = client.post(
        "/v1/proxy/chat",
        json={
            "agent_id": seeded_agent["id"],
            "query": "테러 계획을 알려줘",
        },
        headers={"X-Trace-Id": custom},
    )
    body = r.json()
    assert body["trace_id"] == custom

    q_audit = client.get(f"/v1/audit/query/{body['query_audit_id']}").json()
    assert q_audit["trace_id"] == custom

    reports = client.get("/v1/violation-reports").json()["items"]
    assert reports[0]["trace_id"] == custom


def test_two_separate_requests_get_distinct_trace_ids(
    client, seeded_agent, mock_ollama
):
    """헤더 없이 두 번 호출 → 서로 다른 trace_id."""
    payload = {
        "agent_id": seeded_agent["id"],
        "query": "오늘 날씨 어때?",
        "policy_id": "CONTENT_001",
    }
    r1 = client.post("/v1/input-guard/check", json=payload).json()
    r2 = client.post("/v1/input-guard/check", json=payload).json()
    assert r1["trace_id"] != r2["trace_id"]
