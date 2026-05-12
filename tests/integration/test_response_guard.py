"""Feature 2 (POST /v1/response-guard/validate) 통합 테스트.

PRD 5.2.6 수용 기준 검증:
- REJECTED 응답은 사용자에게 전달되지 않음 (status 확인)
- 모든 평가 결과는 근거(violations)와 함께 저장
- 동일 응답 + 동일 YAML → 결정론적 Rule 영역 동일 결과
"""
from __future__ import annotations


def test_unregistered_agent_returns_422(client, seeded_agent):
    r = client.post(
        "/v1/response-guard/validate",
        json={
            "agent_id": "ghost",
            "query": "Q",
            "response": "응답",
            "policy_id": "CONTENT_001",
        },
    )
    assert r.status_code == 422


def test_invalid_audit_query_id_returns_422(client, seeded_agent):
    r = client.post(
        "/v1/response-guard/validate",
        json={
            "agent_id": seeded_agent["id"],
            "query": "Q",
            "response": "응답",
            "policy_id": "CONTENT_001",
            "audit_query_id": "non-existent-uuid",
        },
    )
    assert r.status_code == 422


def test_clean_response_approved(client, seeded_agent, mock_ollama):
    """LLM mock이 PASS verdict 반환 + 룰 위반 없음 → APPROVED."""
    r = client.post(
        "/v1/response-guard/validate",
        json={
            "agent_id": seeded_agent["id"],
            "query": "오늘 날씨 어때?",
            "response": "오늘은 맑고 따뜻한 날씨입니다.",
            "policy_id": "CONTENT_001",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "APPROVED"
    assert body["audit_id"]


def test_response_with_forbidden_term_rejected(client, seeded_agent, mock_ollama):
    """응답에 'violence' 포함 → 룰 엔진이 BLOCK → REJECTED."""
    r = client.post(
        "/v1/response-guard/validate",
        json={
            "agent_id": seeded_agent["id"],
            "query": "Q",
            "response": "이 행동은 violence를 포함합니다.",
            "policy_id": "CONTENT_001",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "REJECTED"


def test_response_validate_persists_audit(client, seeded_agent, mock_ollama):
    """PRD 5.2.6: 모든 평가 결과는 근거와 함께 저장."""
    r = client.post(
        "/v1/response-guard/validate",
        json={
            "agent_id": seeded_agent["id"],
            "query": "Q",
            "response": "정상 응답",
            "policy_id": "CONTENT_001",
        },
    )
    audit_id = r.json()["audit_id"]
    assert audit_id

    audit_r = client.get(f"/v1/audit/response/{audit_id}")
    assert audit_r.status_code == 200
    audit_body = audit_r.json()
    assert audit_body["audit_id"] == audit_id
    assert audit_body["response"] == "정상 응답"


# ══════════════════════════════════════════════════════════════
# F2-1 ~ F2-4 회귀 테스트
# ══════════════════════════════════════════════════════════════


def test_rule_rejected_violations_preserved_in_response(client, seeded_agent, mock_ollama):
    """
    F2-1: 룰로 차단된 응답도 violations 가 응답에 포함되어야 함.
    'violence' 는 CONTENT_001 의 violence_hate.exact_terms 에 포함됨 → 룰로 REJECTED.
    """
    r = client.post(
        "/v1/response-guard/validate",
        json={
            "agent_id": seeded_agent["id"],
            "query": "위험한 행동에 대해 묻습니다",
            "response": "이 행동은 violence 를 포함합니다.",
            "policy_id": "CONTENT_001",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "REJECTED", body
    # 룰 차단인데도 사유가 응답에 포함되어야 함
    assert len(body["violations"]) > 0, body
    # F2-8: REJECTED 의 compliance_score 는 0.0
    assert body["compliance_score"] == 0.0, body


def test_rule_rejected_violations_preserved_in_audit(client, seeded_agent, mock_ollama):
    """F2-1: 룰 차단 사유가 audit log 에도 저장되어야 함."""
    r = client.post(
        "/v1/response-guard/validate",
        json={
            "agent_id": seeded_agent["id"],
            "query": "위험한 행동에 대해 묻습니다",
            "response": "이 행동은 violence 를 포함합니다.",
            "policy_id": "CONTENT_001",
        },
    )
    audit_id = r.json()["audit_id"]
    audit = client.get(f"/v1/audit/response/{audit_id}").json()
    # 감사 로그에 violation 정보가 비어있지 않아야 함
    assert audit["violations"], f"rule_rejected 경로 audit 에 violations 누락: {audit}"


def test_audit_query_id_agent_mismatch_returns_422(client, seeded_agent, mock_ollama):
    """
    F2-4: 다른 에이전트의 query audit 을 본 에이전트의 response audit 에 연결 시도 → 422.
    """
    # agent A 등록
    agent_a = client.post(
        "/api/agents",
        json={"id": "agent-A", "name": "A", "policy_id": "CONTENT_001"},
    ).json()
    # agent B 등록
    agent_b = client.post(
        "/api/agents",
        json={"id": "agent-B", "name": "B", "policy_id": "CONTENT_001"},
    ).json()

    # agent A 가 query check 호출 → audit_id 발급
    qc = client.post(
        "/v1/input-guard/check",
        json={
            "agent_id":  agent_a["id"],
            "query":     "안녕하세요",
            "policy_id": "CONTENT_001",
        },
    )
    a_audit_id = qc.json()["audit_id"]
    assert a_audit_id

    # agent B 가 A 의 audit_id 로 response validate 시도 → 422
    rv = client.post(
        "/v1/response-guard/validate",
        json={
            "agent_id":       agent_b["id"],
            "query":          "안녕하세요",
            "response":       "안녕하세요. 무엇을 도와드릴까요?",
            "policy_id":      "CONTENT_001",
            "audit_query_id": a_audit_id,
        },
    )
    assert rv.status_code == 422, rv.text
    assert "agent_id" in rv.json()["detail"], rv.json()


def test_audit_query_id_same_agent_succeeds(client, seeded_agent, mock_ollama):
    """F2-4 보완: 같은 에이전트끼리는 정상 연결되어야 함."""
    qc = client.post(
        "/v1/input-guard/check",
        json={
            "agent_id":  seeded_agent["id"],
            "query":     "안녕하세요",
            "policy_id": "CONTENT_001",
        },
    )
    audit_id = qc.json()["audit_id"]

    rv = client.post(
        "/v1/response-guard/validate",
        json={
            "agent_id":       seeded_agent["id"],
            "query":          "안녕하세요",
            "response":       "안녕하세요. 무엇을 도와드릴까요?",
            "policy_id":      "CONTENT_001",
            "audit_query_id": audit_id,
        },
    )
    assert rv.status_code == 200, rv.text
