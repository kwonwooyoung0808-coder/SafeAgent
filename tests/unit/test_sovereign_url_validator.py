"""SOVEREIGN_AI_URL 데이터 주권 가드 단위 테스트.

설계 문서 §4 동작 케이스 표를 그대로 검증.
보안 정책 NIST SP 800-53 SC-7(5) Default-Deny / Allow by Exception.
"""
from __future__ import annotations

import pytest

from src.services.sovereign_ai_client import _validate_sovereign_url


# ──────────────────────────────────────────────────────────────
# 허용 케이스
# ──────────────────────────────────────────────────────────────


class TestAllowed:
    def test_default_localhost(self):
        _validate_sovereign_url("http://localhost:11434")

    def test_default_ollama_service(self):
        _validate_sovereign_url("http://ollama:11434")

    def test_default_docker_host(self):
        _validate_sovereign_url("http://host.docker.internal:11434")

    def test_rfc1918_class_a(self):
        _validate_sovereign_url("http://10.0.0.5:11434")

    def test_rfc1918_class_b(self):
        _validate_sovereign_url("http://172.16.5.10:11434")

    def test_rfc1918_class_c(self):
        _validate_sovereign_url("http://192.168.10.50:11434")

    def test_loopback_ip(self):
        _validate_sovereign_url("http://127.0.0.1:11434")

    def test_explicit_allowed_host_via_env(self, monkeypatch):
        """SOVEREIGN_ALLOWED_HOSTS 에 명시 등록된 호스트 통과 (env 동작 확인)."""
        monkeypatch.setenv(
            "SOVEREIGN_ALLOWED_HOSTS", "localhost,my-internal-llm"
        )
        _validate_sovereign_url("http://my-internal-llm:11434")


# ──────────────────────────────────────────────────────────────
# 차단 케이스 (default-deny)
# ──────────────────────────────────────────────────────────────


class TestBlocked:
    def test_openai_cloud(self):
        with pytest.raises(ValueError, match="허용 목록"):
            _validate_sovereign_url("https://api.openai.com/v1")

    def test_anthropic_cloud(self):
        with pytest.raises(ValueError, match="허용 목록"):
            _validate_sovereign_url("https://api.anthropic.com/v1")

    def test_unknown_new_cloud(self):
        """blocklist 미등록 신규 클라우드도 default-deny 로 자동 차단."""
        with pytest.raises(ValueError, match="허용 목록"):
            _validate_sovereign_url("https://newai.cloud")

    def test_public_ip_rejected(self):
        """공인 IP 는 RFC 1918 사내 대역 아님 → 차단."""
        with pytest.raises(ValueError, match="RFC 1918"):
            _validate_sovereign_url("http://8.8.8.8:11434")

    def test_local_tld_rejected(self):
        """.local TLD 자동 허용 미적용 — Apple mDNS 충돌 방지."""
        with pytest.raises(ValueError, match="허용 목록"):
            _validate_sovereign_url("http://my-server.local")


# ──────────────────────────────────────────────────────────────
# 입력 오류
# ──────────────────────────────────────────────────────────────


class TestInputValidation:
    def test_empty_url_rejected(self):
        with pytest.raises(ValueError, match="비어 있"):
            _validate_sovereign_url("")

    def test_whitespace_only_rejected(self):
        with pytest.raises(ValueError, match="비어 있"):
            _validate_sovereign_url("   ")

    def test_malformed_url_rejected(self):
        """호스트 파싱 불가 입력 — 빈 호스트 또는 default-deny 둘 중 하나."""
        with pytest.raises(ValueError):
            _validate_sovereign_url("not a url at all")
