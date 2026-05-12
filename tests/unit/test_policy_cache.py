"""PolicyCache 단위 테스트 (Phase 3-B)."""
from __future__ import annotations

from pathlib import Path

import pytest

from src.utils.policy_cache import _PolicyCache


@pytest.fixture
def yaml_file() -> Path:
    """실제 운영 중인 정책 YAML 사용 — 스키마 변경에도 자동 호환."""
    p = Path("src/policies/content_policy.yaml").resolve()
    assert p.exists(), f"테스트 전제: {p} 파일이 존재해야 함"
    return p


def test_first_get_is_miss(yaml_file: Path):
    cache = _PolicyCache()
    cache.get("TEST_001", "1.0", str(yaml_file))
    assert cache.stats() == {"size": 1, "hits": 0, "misses": 1}


def test_second_get_is_hit(yaml_file: Path):
    cache = _PolicyCache()
    cache.get("TEST_001", "1.0", str(yaml_file))
    cache.get("TEST_001", "1.0", str(yaml_file))
    s = cache.stats()
    assert s["hits"] == 1
    assert s["misses"] == 1
    assert s["size"] == 1


def test_different_versions_are_separate_entries(yaml_file: Path):
    cache = _PolicyCache()
    cache.get("TEST_001", "1.0", str(yaml_file))
    cache.get("TEST_001", "2.0", str(yaml_file))
    assert cache.stats()["size"] == 2


def test_invalidate_specific_version(yaml_file: Path):
    cache = _PolicyCache()
    cache.get("TEST_001", "1.0", str(yaml_file))
    cache.get("TEST_001", "2.0", str(yaml_file))
    removed = cache.invalidate("TEST_001", "1.0")
    assert removed == 1
    assert cache.stats()["size"] == 1


def test_invalidate_all_versions_of_policy(yaml_file: Path):
    cache = _PolicyCache()
    cache.get("TEST_001", "1.0", str(yaml_file))
    cache.get("TEST_001", "2.0", str(yaml_file))
    cache.get("OTHER_002", "1.0", str(yaml_file))
    removed = cache.invalidate("TEST_001")
    assert removed == 2
    # OTHER_002 는 보존
    assert cache.stats()["size"] == 1


def test_invalidate_unknown_returns_zero(yaml_file: Path):
    cache = _PolicyCache()
    cache.get("TEST_001", "1.0", str(yaml_file))
    assert cache.invalidate("DOES_NOT_EXIST") == 0
    assert cache.invalidate("TEST_001", "999.9.9") == 0


def test_after_invalidate_next_get_is_miss(yaml_file: Path):
    cache = _PolicyCache()
    cache.get("TEST_001", "1.0", str(yaml_file))
    cache.invalidate("TEST_001")
    cache.get("TEST_001", "1.0", str(yaml_file))
    s = cache.stats()
    assert s["misses"] == 2  # 첫 로드 + invalidate 후 재로드


def test_clear_resets_everything(yaml_file: Path):
    cache = _PolicyCache()
    cache.get("TEST_001", "1.0", str(yaml_file))
    cache.get("TEST_001", "1.0", str(yaml_file))
    cache.clear()
    assert cache.stats() == {"size": 0, "hits": 0, "misses": 0}


def test_returns_same_object_on_hit(yaml_file: Path):
    """캐시가 같은 객체 참조를 반환 (불필요한 deepcopy 없음)."""
    cache = _PolicyCache()
    p1 = cache.get("TEST_001", "1.0", str(yaml_file))
    p2 = cache.get("TEST_001", "1.0", str(yaml_file))
    assert p1 is p2
