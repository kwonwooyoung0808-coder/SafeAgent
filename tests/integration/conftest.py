"""
통합 테스트 공용 fixtures.

- client: 매 테스트마다 schema drop/create + lifespan 트리거 (seed 정책 자동 등록)
- mock_ollama: OllamaClient.generate / .chat을 가짜 응답으로 monkeypatch
- seeded_agent: CONTENT_001 정책에 연결된 테스트용 agent 생성
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """
    매 테스트마다 깨끗한 schema + 정책 seed 보장.
    `with TestClient(app)` 패턴으로 lifespan을 실행해 init_db()가 호출됨.

    Phase 4 인증: bootstrap admin 시드가 자동 생성되므로 admin 으로 로그인해
    Authorization 헤더를 기본 주입 — 기존 테스트가 Bearer 없이도 통과되도록.
    """
    # 지연 import: tests/conftest.py가 DATABASE_URL을 redirect한 후에 src.* 로드
    from src.database import models  # noqa: F401 — 모델 등록
    from src.database.connection import Base, engine
    from src.main import app

    # 이전 테스트의 잔여 데이터 제거
    Base.metadata.drop_all(bind=engine)

    # TestClient의 with 블록이 lifespan 실행 → init_db() → create_all + seed_bootstrap_admin
    with TestClient(app) as c:
        # 기존 테스트들이 인증 헤더 없이 작성됐으므로, admin 토큰을 기본 주입.
        login = c.post("/v1/auth/login", json={"username": "admin", "password": "changeme"})
        assert login.status_code == 200, login.text
        token = login.json()["access_token"]
        c.headers["Authorization"] = f"Bearer {token}"
        yield c

    # 종료 후 정리
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def viewer_client(client):
    """viewer 권한 테스트용 — 별도 사용자 생성 후 로그인."""
    from fastapi.testclient import TestClient
    from src.database.connection import SessionLocal
    from src.database.models import UserModel
    from src.core.auth import hash_password
    import uuid

    session = SessionLocal()
    try:
        session.add(UserModel(
            id=f"user-{uuid.uuid4()}",
            username="viewer-test",
            hashed_password=hash_password("ViewerPass123"),
            role="viewer",
            policy_groups=[],
            is_active=True,
        ))
        session.commit()
    finally:
        session.close()

    from src.main import app
    new_client = TestClient(app)
    login = new_client.post(
        "/v1/auth/login",
        json={"username": "viewer-test", "password": "ViewerPass123"},
    )
    assert login.status_code == 200, login.text
    new_client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
    return new_client


@pytest.fixture
def mock_ollama(monkeypatch):
    """
    OllamaClient의 두 메서드를 가짜 응답으로 교체.
    실제 Ollama 서버 없이도 LLM 의존 노드가 deterministic하게 동작.

    기본값:
    - generate() → JudgeEngine이 기대하는 PASS verdict JSON
    - chat() → query_risk_workflow가 기대하는 낮은 risk_score JSON

    필요 시 테스트 내에서 monkeypatch로 추가 override 가능.
    """
    canned_generate = (
        '{"verdict": "PASS", "confidence": 0.95, '
        '"reason": "mocked - 정상 응답", "evidence_text": ""}'
    )
    canned_chat = (
        '{"risk_score": 0.1, "risk_reasons": [], "risk_types": []}'
    )

    canned_sovereign = "안녕하세요. 무엇을 도와드릴까요?"

    async def fake_generate(self, prompt: str, temperature=None) -> str:
        return canned_generate

    async def fake_chat(self, system_prompt, user_message, temperature=None) -> str:
        return canned_chat

    async def fake_sovereign_generate(self, query: str, context=None) -> str:
        return canned_sovereign

    from src.services import ollama_client, sovereign_ai_client
    monkeypatch.setattr(ollama_client.OllamaClient, "generate", fake_generate)
    monkeypatch.setattr(ollama_client.OllamaClient, "chat", fake_chat)
    # Sovereign AI 도 mock — Ollama 가 실행 중이지 않아도 테스트 격리 보장
    monkeypatch.setattr(
        sovereign_ai_client.SovereignAIClient,
        "generate",
        fake_sovereign_generate,
    )

    return {
        "generate": canned_generate,
        "chat": canned_chat,
        "sovereign": canned_sovereign,
    }


@pytest.fixture
def seeded_agent(client):
    """CONTENT_001 정책에 연결된 테스트용 agent 1개 생성.

    Phase 4: 게이트웨이 흐름 (input-guard / response-guard / proxy) 테스트가
    이 fixture 를 통해 진입하므로, agent 생성과 함께 API Key 도 발급해
    client 에 X-API-Key 헤더 주입 — 게이트웨이 엔드포인트도 그대로 호출 가능.
    """
    response = client.post(
        "/api/agents",
        json={
            "id": "agent-test-001",
            "name": "Test Agent",
            "policy_id": "CONTENT_001",
            "status": "ACTIVE",
        },
    )
    assert response.status_code == 201, response.text
    agent = response.json()

    keyresp = client.post(
        f"/api/agents/{agent['id']}/api-keys",
        json={"description": "test"},
    )
    assert keyresp.status_code == 201, keyresp.text
    client.headers["X-API-Key"] = keyresp.json()["api_key"]
    return agent
