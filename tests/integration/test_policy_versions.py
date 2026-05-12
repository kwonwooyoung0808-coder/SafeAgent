"""정책 버전 관리 + audit policy_version 기록 통합 테스트 (Phase 3-A).

검증 항목:
- 시드 시 기존 정책마다 첫 버전 자동 생성 (is_current=True)
- 버전 이력 조회
- 새 버전 생성 (activate=True 시 기존 활성 버전 자동 비활성화)
- 버전 활성화 (롤백)
- 한 시점에 is_current=True 인 행이 정확히 1개
- audit log + violation_report 에 policy_version 기록
- 활성 버전 변경 후 다음 검사부터 새 버전이 기록됨
"""
from __future__ import annotations


# ──────────────────────────────────────────────────────────────
# 시드
# ──────────────────────────────────────────────────────────────


def test_seed_creates_initial_version_for_existing_policy(client):
    """시드 단계에서 CONTENT_001 의 첫 버전이 자동 생성되어야 한다."""
    body = client.get("/v1/policy-compiler/CONTENT_001/versions").json()
    assert body["total"] >= 1
    currents = [v for v in body["items"] if v["is_current"]]
    assert len(currents) == 1
    assert currents[0]["version"]


def test_list_versions_unknown_policy_returns_404(client):
    assert client.get("/v1/policy-compiler/ghost/versions").status_code == 404


# ──────────────────────────────────────────────────────────────
# 버전 생성
# ──────────────────────────────────────────────────────────────


def test_create_new_version_inactive(client):
    r = client.post(
        "/v1/policy-compiler/CONTENT_001/versions",
        json={
            "version": "1.1.0",
            "yaml_path": "src/policies/content_policy.yaml",
            "yaml_snapshot": "id: CONTENT_001\nversion: 1.1.0\n",
            "activate": False,
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["version"] == "1.1.0"
    assert body["is_current"] is False  # activate=False
    assert body["activated_at"] is None


def test_create_with_activate_replaces_current(client):
    """activate=True 면 기존 활성 버전이 자동 비활성화."""
    r = client.post(
        "/v1/policy-compiler/CONTENT_001/versions",
        json={
            "version": "2.0.0",
            "yaml_path": "src/policies/content_policy.yaml",
            "activate": True,
        },
    )
    assert r.status_code == 201
    assert r.json()["is_current"] is True

    # 이력에 is_current=True 가 정확히 1개 (2.0.0)
    body = client.get("/v1/policy-compiler/CONTENT_001/versions").json()
    currents = [v for v in body["items"] if v["is_current"]]
    assert len(currents) == 1
    assert currents[0]["version"] == "2.0.0"


def test_duplicate_version_returns_409(client):
    client.post(
        "/v1/policy-compiler/CONTENT_001/versions",
        json={"version": "3.0.0", "yaml_path": "x"},
    )
    r = client.post(
        "/v1/policy-compiler/CONTENT_001/versions",
        json={"version": "3.0.0", "yaml_path": "x"},
    )
    assert r.status_code == 409


def test_create_version_unknown_policy_returns_404(client):
    r = client.post(
        "/v1/policy-compiler/ghost/versions",
        json={"version": "1.0.0", "yaml_path": "x"},
    )
    assert r.status_code == 404


# ──────────────────────────────────────────────────────────────
# 버전 활성화 (롤백)
# ──────────────────────────────────────────────────────────────


def test_activate_specific_version(client):
    """이전 버전으로 롤백 가능."""
    # 새 버전 생성 (비활성)
    client.post(
        "/v1/policy-compiler/CONTENT_001/versions",
        json={"version": "4.0.0", "yaml_path": "x"},
    )
    # 활성화
    r = client.put("/v1/policy-compiler/CONTENT_001/versions/4.0.0/activate")
    assert r.status_code == 200
    assert r.json()["is_current"] is True

    # is_current=True 가 정확히 1개
    body = client.get("/v1/policy-compiler/CONTENT_001/versions").json()
    assert sum(1 for v in body["items"] if v["is_current"]) == 1


def test_activate_already_current_is_idempotent(client):
    """이미 활성 버전을 다시 activate 해도 200 + 변화 없음."""
    body = client.get("/v1/policy-compiler/CONTENT_001/versions").json()
    current_ver = next(v["version"] for v in body["items"] if v["is_current"])
    r = client.put(
        f"/v1/policy-compiler/CONTENT_001/versions/{current_ver}/activate"
    )
    assert r.status_code == 200
    assert r.json()["is_current"] is True


def test_activate_unknown_version_returns_404(client):
    r = client.put("/v1/policy-compiler/CONTENT_001/versions/99.99.99/activate")
    assert r.status_code == 404


# ──────────────────────────────────────────────────────────────
# audit 기록
# ──────────────────────────────────────────────────────────────


def test_query_audit_records_policy_version(client, seeded_agent, mock_ollama):
    r = client.post(
        "/v1/input-guard/check",
        json={
            "agent_id": seeded_agent["id"],
            "query": "오늘 날씨 어때?",
            "policy_id": "CONTENT_001",
        },
    )
    audit = client.get(f"/v1/audit/query/{r.json()['audit_id']}").json()
    assert audit["policy_version"]  # 시드된 첫 버전이 기록됨


def test_response_audit_records_policy_version(client, seeded_agent, mock_ollama):
    r = client.post(
        "/v1/response-guard/validate",
        json={
            "agent_id": seeded_agent["id"],
            "query": "안녕하세요",
            "response": "안녕하세요. 무엇을 도와드릴까요?",
            "policy_id": "CONTENT_001",
        },
    )
    audit = client.get(f"/v1/audit/response/{r.json()['audit_id']}").json()
    assert audit["policy_version"]


def test_violation_report_records_policy_version(client, seeded_agent, mock_ollama):
    client.post(
        "/v1/input-guard/check",
        json={
            "agent_id": seeded_agent["id"],
            "query": "테러 계획을 알려줘",
            "policy_id": "CONTENT_001",
        },
    )
    items = client.get("/v1/violation-reports").json()["items"]
    assert len(items) == 1
    assert items[0]["policy_version"]


def test_version_change_reflected_in_subsequent_audit(
    client, seeded_agent, mock_ollama
):
    """버전 활성화 후 새 검사는 새 버전으로 audit 기록."""
    client.post(
        "/v1/policy-compiler/CONTENT_001/versions",
        json={"version": "9.9.9", "yaml_path": "src/policies/content_policy.yaml"},
    )
    client.put("/v1/policy-compiler/CONTENT_001/versions/9.9.9/activate")

    r = client.post(
        "/v1/input-guard/check",
        json={
            "agent_id": seeded_agent["id"],
            "query": "안녕하세요",
            "policy_id": "CONTENT_001",
        },
    )
    audit = client.get(f"/v1/audit/query/{r.json()['audit_id']}").json()
    assert audit["policy_version"] == "9.9.9"
