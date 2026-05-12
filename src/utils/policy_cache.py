"""정책 메모리 캐시 (Phase 3-B).

핫패스 (F1/F2) 가 매 요청마다 디스크에서 동일 YAML 을 반복 로드하는 비용을 제거한다.

설계:
- 프로세스 단위 싱글톤
- 키: (policy_id, version) — 버전이 바뀌면 별도 엔트리 (audit 추적과 호환)
- 무효화: 정책 활성화/비활성화, 새 버전 활성화 시 라우터에서 명시적 호출
  → TTL 미적용. invalidate 누락은 단위 테스트로 강제.
- 동시성: RLock 으로 dict 의 복합 연산 (조회 + 부재 시 채움) 보호.
  단일 연산 (dict.get/dict.setdefault) 자체는 GIL 하에서 atomic 하지만,
  read-then-write 흐름은 합쳐진 임계영역이므로 명시적 lock 필요.

⚠️ 한계 — 멀티 워커/분산 환경 미지원
    각 프로세스가 자체 캐시를 가지므로 Gunicorn workers > 1 또는 Kubernetes
    scale-out 환경에서는 일관성 붕괴. 그 경우 Redis 등 외부 캐시 계층으로 교체 필요.
    현재 SafeAgent_Manager 는 자체 호스팅 단일 워커 가정.
"""
from __future__ import annotations

import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.schemas.policy import Policy

from src.utils.yaml_loader import load_policy as _load_policy_uncached


class _PolicyCache:
    """프로세스 단위 정책 캐시 — 명시적 invalidate 까지 보존."""

    def __init__(self) -> None:
        self._cache: dict[tuple[str, str], "Policy"] = {}
        self._lock = threading.RLock()
        # 진단용 카운터 (운영 모니터링/테스트용)
        self.hits = 0
        self.misses = 0

    def get(self, policy_id: str, version: str, yaml_path: str) -> "Policy":
        """캐시에서 Policy 객체 조회. miss 시 yaml_path 로 디스크 로드 + 캐시.

        디스크 I/O 는 lock 밖에서 수행해 다른 키 조회를 막지 않음. 동일 키에 대해
        2개 스레드가 동시 miss 하면 중복 로드 가능하나 결과는 idempotent.
        """
        key = (policy_id, version)
        with self._lock:
            cached = self._cache.get(key)
            if cached is not None:
                self.hits += 1
                return cached
            self.misses += 1

        # 디스크 로드는 lock 밖
        policy = _load_policy_uncached(yaml_path)

        with self._lock:
            # setdefault: 다른 스레드가 먼저 채웠다면 그것을 유지
            return self._cache.setdefault(key, policy)

    def invalidate(self, policy_id: str, version: str | None = None) -> int:
        """특정 (policy_id, version) 또는 policy_id 의 모든 버전 무효화.

        Returns: 제거된 엔트리 수.
        """
        with self._lock:
            if version is not None:
                removed = self._cache.pop((policy_id, version), None)
                return 1 if removed is not None else 0

            # policy_id 의 모든 버전 제거 — dict 재생성으로 atomic 의도 명확
            before = len(self._cache)
            self._cache = {
                k: v for k, v in self._cache.items() if k[0] != policy_id
            }
            return before - len(self._cache)

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
            self.hits = 0
            self.misses = 0

    def stats(self) -> dict[str, int]:
        with self._lock:
            return {
                "size": len(self._cache),
                "hits": self.hits,
                "misses": self.misses,
            }


# 싱글톤 인스턴스
_policy_cache_singleton = _PolicyCache()


def get_policy_cache() -> _PolicyCache:
    return _policy_cache_singleton
