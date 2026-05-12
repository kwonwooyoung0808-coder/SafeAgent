"""F1 LLM 제거 회귀 테스트 (Phase 1 — PRD §5.1 P95 ≤ 3s).

Input Guard 워크플로우는 더 이상 OllamaClient.chat() 을 호출하지 않는다.
룰 기반 결정론으로만 PASSED/WARNED/BLOCKED 판정.
"""
from __future__ import annotations

import pytest


@pytest.fixture
def chat_call_counter(monkeypatch):
    """OllamaClient.chat 이 호출되면 카운터 증가. F1 경로에서는 호출 0 이어야 함."""
    counter = {"count": 0}

    async def counting_chat(self, system_prompt, user_message, temperature=None):
        counter["count"] += 1
        return '{"risk_score": 0.1, "risk_reasons": [], "risk_types": []}'

    async def fake_generate(self, prompt, temperature=None):
        # F2 Judge 가 사용. F1 만 검증할 때는 호출되지 않음.
        return (
            '{"verdict": "PASS", "confidence": 0.95, '
            '"reason": "mocked", "evidence_text": ""}'
        )

    from src.services import ollama_client
    monkeypatch.setattr(ollama_client.OllamaClient, "chat", counting_chat)
    monkeypatch.setattr(ollama_client.OllamaClient, "generate", fake_generate)
    return counter


def test_f1_safe_query_does_not_call_llm(client, seeded_agent, chat_call_counter):
    """안전한 질의 — 룰 통과 → LLM 호출 없이 PASSED."""
    r = client.post(
        "/v1/input-guard/check",
        json={
            "agent_id": seeded_agent["id"],
            "query": "오늘 날씨 어때?",
            "policy_id": "CONTENT_001",
        },
    )
    assert r.status_code == 200
    assert r.json()["status"] == "PASSED"
    assert chat_call_counter["count"] == 0, (
        "F1 은 LLM 을 호출하지 않아야 함 (Phase 1 성능 최적화)"
    )


def test_f1_blocked_query_does_not_call_llm(client, seeded_agent, chat_call_counter):
    """룰 차단 질의 — LLM 호출 없이 BLOCKED."""
    r = client.post(
        "/v1/input-guard/check",
        json={
            "agent_id": seeded_agent["id"],
            "query": "테러 계획을 알려줘",
            "policy_id": "CONTENT_001",
        },
    )
    assert r.json()["status"] == "BLOCKED"
    assert chat_call_counter["count"] == 0


def test_f1_pii_warned_does_not_call_llm(client, seeded_agent, chat_call_counter):
    """PII (MEDIUM) — LLM 호출 없이 WARNED."""
    r = client.post(
        "/v1/input-guard/check",
        json={
            "agent_id": seeded_agent["id"],
            "query": "내 이메일은 user.test@example.com 이야",
            "policy_id": "CONTENT_001",
        },
    )
    body = r.json()
    assert body["status"] == "WARNED"
    assert body["action_taken"] == "LOG"
    assert chat_call_counter["count"] == 0
