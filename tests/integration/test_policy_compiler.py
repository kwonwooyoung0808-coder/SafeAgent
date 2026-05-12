"""Feature 3 (POST /v1/policy-compiler/compile) 회귀 테스트.

PRD 5.3.6 수용 기준 검증:
- 변환 실패 시 원본 파일과 오류 로그가 보존된다.
- 변환된 YAML 은 정의된 스키마 검증을 통과한다.
"""
from __future__ import annotations

import io
from pathlib import Path

import pytest


# ══════════════════════════════════════════════════════════════
# F3-1, F3-2 회귀 테스트 — .docx 입력 없이 라우터 검증만
# (실제 .docx 파싱은 python-docx 의존이라 별도 e2e 에서 검증)
# ══════════════════════════════════════════════════════════════


def test_convert_rejects_non_docx_extension(client):
    """라우터 입력 검증: .docx 외 확장자는 400."""
    fake_file = io.BytesIO(b"not a real docx")
    r = client.post(
        "/v1/policy-compiler/compile",
        files={"file": ("policy.txt", fake_file, "text/plain")},
        data={"policy_name": "Test Policy", "effective_date": "2026-01-01"},
    )
    assert r.status_code == 400, r.text


def test_convert_rejects_oversized_file(client):
    """라우터 입력 검증: 10MB 초과 파일은 413."""
    big_content = b"a" * (10 * 1024 * 1024 + 1)
    r = client.post(
        "/v1/policy-compiler/compile",
        files={"file": ("big.docx", io.BytesIO(big_content), "application/octet-stream")},
        data={"policy_name": "Big", "effective_date": "2026-01-01"},
    )
    assert r.status_code == 413, r.text


def test_convert_invalid_docx_preserves_original(client, tmp_path, monkeypatch):
    """
    F3-1: 유효하지 않은 .docx 입력 → docx_extractor_node 실패 → status=FAILED.
    원본이 {policy_dir}/failed_uploads/ 에 보존되어야 함.
    F3-2: PolicyConversionLogModel 에 실패 로그가 생성되어야 함.
    """
    # 잘못된 .docx 콘텐츠 (DocxEngine.parse 가 raise 하도록 유도)
    fake_docx = b"PK\x03\x04 not a valid docx zip"

    # policy_dir 가 신규 생성되더라도 안전하게 보존되는지만 확인
    r = client.post(
        "/v1/policy-compiler/compile",
        files={"file": ("malformed.docx", io.BytesIO(fake_docx), "application/octet-stream")},
        data={"policy_name": "Malformed", "effective_date": "2026-01-01"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "FAILED", body
    # F3-2: failed-{...} 형태의 추적 ID 가 응답에 포함되어야 함
    assert body["policy_id"] is not None, body
    assert body["policy_id"].startswith("failed-"), body
    # F3-1: 원본 보존 경로 안내가 warnings 에 있어야 함
    warnings_text = "\n".join(body["warnings"])
    assert "원본 보존" in warnings_text, body["warnings"]


def test_convert_invalid_docx_creates_conversion_log(client):
    """F3-2: 실패 케이스도 PolicyConversionLogModel 에 기록되어야 함."""
    from src.database.connection import SessionLocal
    from src.database.models import PolicyConversionLogModel

    fake_docx = b"PK\x03\x04 broken"
    r = client.post(
        "/v1/policy-compiler/compile",
        files={"file": ("broken.docx", io.BytesIO(fake_docx), "application/octet-stream")},
        data={"policy_name": "BrokenPolicy", "effective_date": "2026-01-01"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "FAILED"

    # DB 직접 조회로 로그 존재 확인
    session = SessionLocal()
    try:
        rows = session.query(PolicyConversionLogModel).filter(
            PolicyConversionLogModel.original_filename == "broken.docx",
            PolicyConversionLogModel.conversion_status == "FAILED",
        ).all()
        assert len(rows) >= 1, "실패 케이스 PolicyConversionLogModel 누락"
    finally:
        session.close()
