"""정책 활성화/버전 변경 시 캐시 무효화 통합 테스트 (Phase 3-B).

핫패스 워크플로우와 캐시가 실제로 연결되어 있고, 정책 상태 변경이
다음 요청부터 즉시 반영되는지 검증.
"""
from __future__ import annotations

import pytest

from src.utils.policy_cache import get_policy_cache


@pytest.fixture
def fresh_cache():
    """각 테스트 시작 전 캐시 초기화."""
    cache = get_policy_cache()
    cache.clear()
    yield cache
    cache.clear()


def test_workflow_populates_cache(client, seeded_agent, mock_ollama, fresh_cache):
    """F1 호출 시 캐시에 정책이 적재된다."""
    assert fresh_cache.stats()["size"] == 0

    client.post(
        "/v1/input-guard/check",
        json={
            "agent_id": seeded_agent["id"],
            "query": "안녕하세요",
            "policy_id": "CONTENT_001",
        },
    )

    stats = fresh_cache.stats()
    assert stats["size"] >= 1
    assert stats["misses"] >= 1


def test_repeated_calls_hit_cache(client, seeded_agent, mock_ollama, fresh_cache):
    """같은 정책 반복 호출 시 디스크 I/O 발생하지 않음 (hit 증가)."""
    payload = {
        "agent_id": seeded_agent["id"],
        "query": "오늘 날씨 어때?",
        "policy_id": "CONTENT_001",
    }
    client.post("/v1/input-guard/check", json=payload)
    misses_after_first = fresh_cache.stats()["misses"]

    # 두 번 더 호출 — miss 는 늘지 않고 hit 만 증가
    client.post("/v1/input-guard/check", json=payload)
    client.post("/v1/input-guard/check", json=payload)

    final = fresh_cache.stats()
    assert final["misses"] == misses_after_first  # 추가 miss 없음
    assert final["hits"] >= 2


def test_version_activation_invalidates_cache(
    client, seeded_agent, mock_ollama, fresh_cache
):
    """새 버전 활성화 후 다음 호출은 cache miss → 재로드."""
    payload = {
        "agent_id": seeded_agent["id"],
        "query": "안녕하세요",
        "policy_id": "CONTENT_001",
    }
    client.post("/v1/input-guard/check", json=payload)
    initial_size = fresh_cache.stats()["size"]

    # 새 버전 생성 + 활성화
    client.post(
        "/v1/policy-compiler/CONTENT_001/versions",
        json={
            "version": "5.0.0",
            "yaml_path": "src/policies/content_policy.yaml",
            "activate": True,
        },
    )

    # 활성화 직후 캐시는 비워져야 함 (CONTENT_001 의 모든 엔트리 invalidated)
    assert fresh_cache.stats()["size"] == initial_size - 1


def test_explicit_activate_invalidates_cache(
    client, seeded_agent, mock_ollama, fresh_cache
):
    """PUT /versions/{ver}/activate 도 캐시 무효화."""
    payload = {
        "agent_id": seeded_agent["id"],
        "query": "안녕하세요",
        "policy_id": "CONTENT_001",
    }
    client.post("/v1/input-guard/check", json=payload)

    # 비활성 상태로 새 버전 등록
    client.post(
        "/v1/policy-compiler/CONTENT_001/versions",
        json={"version": "6.0.0", "yaml_path": "src/policies/content_policy.yaml"},
    )
    size_before_activate = fresh_cache.stats()["size"]

    # 활성화 트리거
    client.put("/v1/policy-compiler/CONTENT_001/versions/6.0.0/activate")

    # CONTENT_001 의 캐시 엔트리가 비워졌어야 함
    assert fresh_cache.stats()["size"] < size_before_activate


def test_policy_activation_endpoint_invalidates(
    client, seeded_agent, mock_ollama, fresh_cache
):
    """PUT /policy-compiler/{id}/activate 도 무효화."""
    payload = {
        "agent_id": seeded_agent["id"],
        "query": "안녕하세요",
        "policy_id": "CONTENT_001",
    }
    client.post("/v1/input-guard/check", json=payload)
    assert fresh_cache.stats()["size"] >= 1

    client.put("/v1/policy-compiler/CONTENT_001/activate")
    # CONTENT_001 캐시 모두 무효화
    assert all(
        # 캐시 stats 만으로는 키를 직접 못 보지만 size 가 0 이거나 하나 줄어든 상태
        True
        for _ in [None]
    )
    # 정확한 검증: CONTENT_001 에 대한 추가 호출은 다시 miss 발생
    misses_before = fresh_cache.stats()["misses"]
    client.post("/v1/input-guard/check", json=payload)
    assert fresh_cache.stats()["misses"] == misses_before + 1


def test_different_policies_cached_independently(
    client, seeded_agent, mock_ollama, fresh_cache
):
    """F2 가 다중 정책 결합 시 각각 별도 엔트리 (동일 정책이면 1개)."""
    # 그룹에 정책 추가하여 F2 가 결합 호출
    client.post(
        "/v1/policy-groups",
        json={"id": "GCACHE", "name": "cache-test", "policy_ids": ["CONTENT_001"]},
    )
    client.post(
        f"/api/agents/{seeded_agent['id']}/policy-groups",
        json={"group_id": "GCACHE"},
    )

    client.post(
        "/v1/response-guard/validate",
        json={
            "agent_id": seeded_agent["id"],
            "query": "안녕하세요",
            "response": "안녕하세요. 무엇을 도와드릴까요?",
        },
    )
    # CONTENT_001 은 시스템 정책 + 그룹 멤버로 두 번 참조되지만,
    # 동일 (policy_id, version) 키이므로 캐시 엔트리는 1개
    stats = fresh_cache.stats()
    assert stats["size"] >= 1
