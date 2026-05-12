"""Policy Groups + Agent 매핑 통합 테스트 (Phase 2-C).

검증 항목:
- 그룹 CRUD + 멤버 일괄 교체
- Agent ↔ Group 다대다 매핑
- F2 정책 결합에 그룹 멤버 정책이 포함되는지
- 비활성/존재하지 않는 정책으로 그룹 만들면 422
- 그룹 삭제 시 매핑 자동 정리 (FK CASCADE)
"""
from __future__ import annotations


# ──────────────────────────────────────────────────────────────
# 그룹 CRUD
# ──────────────────────────────────────────────────────────────


def test_create_empty_group(client):
    r = client.post(
        "/v1/policy-groups",
        json={"id": "GRP_HR", "name": "HR 부서", "description": "인사 정책"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["id"] == "GRP_HR"
    assert body["policy_ids"] == []


def test_create_group_with_members(client):
    r = client.post(
        "/v1/policy-groups",
        json={"id": "GRP_SEC", "name": "보안", "policy_ids": ["CONTENT_001"]},
    )
    assert r.status_code == 201
    assert r.json()["policy_ids"] == ["CONTENT_001"]


def test_create_group_with_invalid_policy_returns_422(client):
    r = client.post(
        "/v1/policy-groups",
        json={"id": "GRP_BAD", "name": "잘못된 그룹", "policy_ids": ["DOES_NOT_EXIST"]},
    )
    assert r.status_code == 422


def test_create_group_duplicate_id_returns_409(client):
    client.post("/v1/policy-groups", json={"id": "GRP_DUP", "name": "중복"})
    r = client.post("/v1/policy-groups", json={"id": "GRP_DUP", "name": "중복2"})
    assert r.status_code == 409


def test_create_group_auto_id(client):
    r = client.post("/v1/policy-groups", json={"name": "자동 ID"})
    assert r.status_code == 201
    assert r.json()["id"]  # UUID 자동 발급


def test_list_groups(client):
    client.post("/v1/policy-groups", json={"id": "GA", "name": "A"})
    client.post("/v1/policy-groups", json={"id": "GB", "name": "B"})
    body = client.get("/v1/policy-groups").json()
    assert body["total"] == 2
    ids = [item["id"] for item in body["items"]]
    assert {"GA", "GB"} <= set(ids)


def test_get_group_includes_member_policy_ids(client):
    client.post(
        "/v1/policy-groups",
        json={"id": "GR1", "name": "G", "policy_ids": ["CONTENT_001"]},
    )
    body = client.get("/v1/policy-groups/GR1").json()
    assert body["policy_ids"] == ["CONTENT_001"]


def test_get_unknown_group_returns_404(client):
    assert client.get("/v1/policy-groups/ghost").status_code == 404


def test_delete_group(client):
    client.post("/v1/policy-groups", json={"id": "GD", "name": "delete"})
    r = client.delete("/v1/policy-groups/GD")
    assert r.status_code == 204
    assert client.get("/v1/policy-groups/GD").status_code == 404


def test_delete_unknown_group_returns_404(client):
    assert client.delete("/v1/policy-groups/ghost").status_code == 404


def test_update_members_set_semantics(client):
    """PUT 은 set semantics — 기존 멤버 전체 교체."""
    client.post(
        "/v1/policy-groups",
        json={"id": "GU", "name": "u", "policy_ids": ["CONTENT_001"]},
    )
    r = client.put("/v1/policy-groups/GU/members", json={"policy_ids": []})
    assert r.status_code == 200
    assert r.json()["policy_ids"] == []


def test_update_members_invalid_policy_returns_422(client):
    client.post("/v1/policy-groups", json={"id": "GV", "name": "v"})
    r = client.put(
        "/v1/policy-groups/GV/members",
        json={"policy_ids": ["NOT_A_POLICY"]},
    )
    assert r.status_code == 422


# ──────────────────────────────────────────────────────────────
# Agent ↔ Group 매핑
# ──────────────────────────────────────────────────────────────


def test_assign_group_to_agent(client, seeded_agent):
    client.post("/v1/policy-groups", json={"id": "GX", "name": "X"})
    r = client.post(
        f"/api/agents/{seeded_agent['id']}/policy-groups",
        json={"group_id": "GX"},
    )
    assert r.status_code == 201
    assert r.json()["assigned"] is True


def test_assign_unknown_group_returns_404(client, seeded_agent):
    r = client.post(
        f"/api/agents/{seeded_agent['id']}/policy-groups",
        json={"group_id": "ghost"},
    )
    assert r.status_code == 404


def test_assign_to_unknown_agent_returns_404(client):
    client.post("/v1/policy-groups", json={"id": "GY", "name": "Y"})
    r = client.post("/api/agents/ghost-agent/policy-groups", json={"group_id": "GY"})
    assert r.status_code == 404


def test_assign_duplicate_returns_409(client, seeded_agent):
    client.post("/v1/policy-groups", json={"id": "GZ", "name": "Z"})
    client.post(f"/api/agents/{seeded_agent['id']}/policy-groups", json={"group_id": "GZ"})
    r = client.post(
        f"/api/agents/{seeded_agent['id']}/policy-groups",
        json={"group_id": "GZ"},
    )
    assert r.status_code == 409


def test_list_agent_groups(client, seeded_agent):
    client.post(
        "/v1/policy-groups",
        json={"id": "G1", "name": "그룹1", "policy_ids": ["CONTENT_001"]},
    )
    client.post("/v1/policy-groups", json={"id": "G2", "name": "그룹2"})
    client.post(f"/api/agents/{seeded_agent['id']}/policy-groups", json={"group_id": "G1"})
    client.post(f"/api/agents/{seeded_agent['id']}/policy-groups", json={"group_id": "G2"})

    body = client.get(f"/api/agents/{seeded_agent['id']}/policy-groups").json()
    ids = {g["group_id"] for g in body}
    assert ids == {"G1", "G2"}
    g1 = next(g for g in body if g["group_id"] == "G1")
    assert g1["policy_ids"] == ["CONTENT_001"]


def test_create_agent_assigns_company_and_department_groups(client):
    client.post("/v1/policy-groups", json={"id": "GLOBAL_COMPANY_RULES", "name": "Company"})
    client.post("/v1/policy-groups", json={"id": "DEPT_LEGAL", "name": "Legal"})

    r = client.post(
        "/api/agents",
        json={
            "id": "agent-dept-001",
            "name": "Dept Agent",
            "department_group_id": "DEPT_LEGAL",
        },
    )

    assert r.status_code == 201, r.text
    assert r.json()["policy_group_ids"] == ["GLOBAL_COMPANY_RULES", "DEPT_LEGAL"]


def test_replace_agent_groups_set_semantics(client, seeded_agent):
    client.post("/v1/policy-groups", json={"id": "GLOBAL_COMPANY_RULES", "name": "Company"})
    client.post("/v1/policy-groups", json={"id": "DEPT_SALES", "name": "Sales"})
    client.post("/v1/policy-groups", json={"id": "EXCEPTION_A", "name": "Exception"})

    r = client.put(
        f"/api/agents/{seeded_agent['id']}/policy-groups",
        json={
            "department_group_id": "DEPT_SALES",
            "policy_group_ids": ["EXCEPTION_A"],
        },
    )

    assert r.status_code == 200, r.text
    assert r.json()["policy_group_ids"] == [
        "GLOBAL_COMPANY_RULES",
        "DEPT_SALES",
        "EXCEPTION_A",
    ]


def test_unassign_group(client, seeded_agent):
    client.post("/v1/policy-groups", json={"id": "GUN", "name": "un"})
    client.post(f"/api/agents/{seeded_agent['id']}/policy-groups", json={"group_id": "GUN"})

    r = client.delete(f"/api/agents/{seeded_agent['id']}/policy-groups/GUN")
    assert r.status_code == 204

    body = client.get(f"/api/agents/{seeded_agent['id']}/policy-groups").json()
    assert body == []


def test_unassign_nonexistent_mapping_returns_404(client, seeded_agent):
    client.post("/v1/policy-groups", json={"id": "GNE", "name": "ne"})
    r = client.delete(f"/api/agents/{seeded_agent['id']}/policy-groups/GNE")
    assert r.status_code == 404


def test_delete_group_cascade_clears_mapping(client, seeded_agent):
    """그룹 삭제 시 FK CASCADE 로 매핑도 자동 정리."""
    client.post("/v1/policy-groups", json={"id": "GCS", "name": "cascade"})
    client.post(f"/api/agents/{seeded_agent['id']}/policy-groups", json={"group_id": "GCS"})

    client.delete("/v1/policy-groups/GCS")

    body = client.get(f"/api/agents/{seeded_agent['id']}/policy-groups").json()
    assert body == []


# ──────────────────────────────────────────────────────────────
# F2 통합: 그룹 멤버 정책이 응답 검증에 적용되는지
# ──────────────────────────────────────────────────────────────


def test_f2_uses_group_member_policies(client, seeded_agent, mock_ollama):
    """
    그룹에 CONTENT_001 추가 → agent 에 그룹 할당 → F2 호출.
    request.policy_id 없이도 그룹 멤버 정책으로 검증 가능해야 한다.
    """
    client.post(
        "/v1/policy-groups",
        json={"id": "GF2", "name": "F2 group", "policy_ids": ["CONTENT_001"]},
    )
    client.post(f"/api/agents/{seeded_agent['id']}/policy-groups", json={"group_id": "GF2"})

    r = client.post(
        "/v1/response-guard/validate",
        json={
            "agent_id": seeded_agent["id"],
            "query": "안녕하세요",
            "response": "안녕하세요. 무엇을 도와드릴까요?",
        },
    )
    # CONTENT_001 + 그룹 멤버에도 CONTENT_001 (중복 제거됨) → 정상 검증
    assert r.status_code == 200
    assert r.json()["status"] in ("APPROVED", "FLAGGED")
