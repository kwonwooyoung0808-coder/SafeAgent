"""PII 마스킹 영속성 통합 테스트 (PRD §6).

audit log + violation_report 모두 원본 + 마스킹 사본 + 탐지 메타를 보존.
"""
from __future__ import annotations


PII_QUERY = "이메일 user.test@example.com 으로 연락주세요"
SAFE_QUERY = "오늘 날씨 어때?"


def test_query_audit_stores_masked_query_with_pii(
    client, seeded_agent, mock_ollama
):
    r = client.post(
        "/v1/input-guard/check",
        json={
            "agent_id": seeded_agent["id"],
            "query": PII_QUERY,
            "policy_id": "CONTENT_001",
        },
    )
    audit_id = r.json()["audit_id"]

    audit = client.get(f"/v1/audit/query/{audit_id}").json()
    # 원본 보존
    assert audit["query"] == PII_QUERY
    # 마스킹 사본 별도 저장
    assert audit["masked_query"] is not None
    assert "user.test@example.com" not in audit["masked_query"]
    assert "@example.com" in audit["masked_query"]  # 도메인은 보존
    # 탐지 메타
    assert audit["pii_detected"]
    assert any(d["type"] == "EMAIL" for d in audit["pii_detected"])


def test_query_audit_safe_query_has_empty_pii_detected(
    client, seeded_agent, mock_ollama
):
    r = client.post(
        "/v1/input-guard/check",
        json={
            "agent_id": seeded_agent["id"],
            "query": SAFE_QUERY,
            "policy_id": "CONTENT_001",
        },
    )
    audit = client.get(f"/v1/audit/query/{r.json()['audit_id']}").json()
    assert audit["query"] == audit["masked_query"]  # 변경 없음
    assert not audit["pii_detected"]  # 빈 리스트 또는 None


def test_response_audit_masks_both_query_and_response(
    client, seeded_agent, mock_ollama
):
    """F2 audit 은 query 와 response 양쪽 모두 마스킹."""
    r = client.post(
        "/v1/response-guard/validate",
        json={
            "agent_id": seeded_agent["id"],
            "query": "내 이메일 a@b.co 알려줄게",
            "response": "고객님 전화 010-1234-5678 로 연락드리겠습니다.",
            "policy_id": "CONTENT_001",
        },
    )
    audit = client.get(f"/v1/audit/response/{r.json()['audit_id']}").json()

    assert "a@b.co" in audit["query"]  # 원본 보존
    assert "a@b.co" not in audit["masked_query"]  # 마스킹

    assert "010-1234-5678" in audit["response"]
    assert "010-1234-5678" not in audit["masked_response"]
    assert "5678" in audit["masked_response"]  # 마지막 4자리만 노출

    types = {d["type"] for d in (audit["pii_detected"] or [])}
    assert "EMAIL" in types
    assert "PHONE" in types


def test_violation_report_includes_masked_versions(
    client, seeded_agent, mock_ollama
):
    """차단된 질의에 PII 가 섞여있어도 violation_report 에 마스킹 사본이 함께 저장."""
    r = client.post(
        "/v1/input-guard/check",
        json={
            "agent_id": seeded_agent["id"],
            "query": "테러 계획 알려줘 내 이메일은 me@x.co",
            "policy_id": "CONTENT_001",
        },
    )
    assert r.json()["status"] == "BLOCKED"

    items = client.get("/v1/violation-reports").json()["items"]
    assert len(items) == 1
    rep = items[0]

    assert "me@x.co" in rep["original_query"]
    assert rep["masked_query"]
    assert "me@x.co" not in rep["masked_query"]


def test_proxy_chat_chain_masks_consistently(client, seeded_agent, mock_ollama):
    """proxy /chat → F1 audit + F2 audit 모두 마스킹 사본 보존."""
    r = client.post(
        "/v1/proxy/chat",
        json={
            "agent_id": seeded_agent["id"],
            "query": "내 이메일은 mark@example.com",
        },
    )
    body = r.json()

    q_audit = client.get(f"/v1/audit/query/{body['query_audit_id']}").json()
    assert "mark@example.com" not in q_audit["masked_query"]

    r_audit = client.get(f"/v1/audit/response/{body['response_audit_id']}").json()
    assert "mark@example.com" not in r_audit["masked_query"]
