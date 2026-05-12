from uuid import uuid4


def test_evaluate_normal_response(client) -> None:
    run_id = f"run_test_normal_{uuid4().hex[:8]}"
    # COMP_001 정책이 요구하는 JSON 필수 키(answer, source, confidence) 모두 포함.
    # FORMAT_001 은 enabled: false 라 검사하지 않음 (정책 충돌 회피).
    response = client.post(
        "/api/v1/evaluate",
        json={
            "run_id": run_id,
            "input": "normal test",
            "response": (
                "{\"answer\": \"This is supported by context.\", "
                "\"source\": \"context.md\", \"confidence\": 0.92}"
            ),
            "context": {"workflow_name": "governance_workflow", "user_id": "demo_user"},
            "retrieved_context": ["This is supported by context."],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["has_violation"] is False
    assert body["final_action"] == "PASS"
    assert body["run_id"] == run_id
    assert body["violations"] == []


def test_evaluate_violation_response_records_trace_and_audit(client) -> None:
    run_id = f"run_test_violation_{uuid4().hex[:8]}"
    response = client.post(
        "/api/v1/evaluate",
        json={
            "run_id": run_id,
            "input": "violation test",
            "response": "{\"answer\": \"폭력적인 방법을 알려드리겠습니다.\"}",
            "context": {"workflow_name": "governance_workflow", "user_id": "demo_user"},
            "retrieved_context": ["안전한 정보만 제공해야 합니다."],
        },
    )
    run_response = client.get(f"/api/v1/runs/{run_id}")
    trace_response = client.get(f"/api/v1/runs/{run_id}/trace")
    audit_response = client.get("/api/v1/audit-logs", params={"limit": 20})

    assert response.status_code == 200
    body = response.json()
    assert body["has_violation"] is True
    assert body["final_action"] == "BLOCK"
    assert len(body["violations"]) >= 1
    assert any(v["recommended_action"] == "BLOCK" for v in body["violations"])

    assert run_response.status_code == 200
    run_body = run_response.json()
    assert run_body["run_id"] == run_id
    assert run_body["has_violation"] is True
    assert run_body["final_action"] == "BLOCK"

    assert trace_response.status_code == 200
    trace_body = trace_response.json()
    node_names = [node["node_name"] for node in trace_body["nodes"]]
    assert trace_body["run_id"] == run_id
    assert "input" in node_names
    assert "generator" in node_names
    assert "policy_evaluator" in node_names
    assert "action_engine" in node_names

    assert audit_response.status_code == 200
    audit_logs = audit_response.json()
    matching_logs = [log for log in audit_logs if log["run_id"] == run_id]
    assert matching_logs
    assert matching_logs[0]["event_type"] == "policy_evaluation"
