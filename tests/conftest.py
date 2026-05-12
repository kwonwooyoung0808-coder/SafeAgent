"""
프로젝트 전역 pytest 설정.

운영 DATABASE_URL을 그대로 쓰지 않고 'safeagent_test' DB로 자동 리다이렉트해서
운영 DB(safeagent)와 완전히 격리된 상태로 테스트를 수행합니다.

사전 준비 (1회):
    psql -U postgres -p 5433 -h localhost -c "CREATE DATABASE safeagent_test;"

설계 원칙 (코드 리뷰 반영):
- python-dotenv로 .env 안전하게 파싱 (따옴표/escape 처리)
- SQLAlchemy make_url로 driver-aware URL 변환
- TEST_DATABASE_URL 명시적 우선
- 정확 매칭 가드 (substring match 금지)
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.engine.url import make_url

# ── ① .env 로드 (python-dotenv) ─────────────────────────────────
# override=False: 이미 OS 환경변수에 있으면 .env가 덮어쓰지 않음
# CI/CD에서 환경변수 직접 주입하는 경우와 호환
_PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(_PROJECT_ROOT / ".env", override=False)


# ── ② 테스트 DB URL 결정 ────────────────────────────────────────
# 우선순위:
#   1. TEST_DATABASE_URL이 명시되어 있으면 그것을 사용 (CI/CD 또는 명시 분리)
#   2. 그 외에는 운영 DATABASE_URL의 dbname만 'safeagent_test'로 교체
def _resolve_test_database_url() -> str:
    explicit = os.environ.get("TEST_DATABASE_URL")
    if explicit:
        return explicit

    prod_url = os.environ.get("DATABASE_URL")
    if not prod_url:
        raise RuntimeError(
            "DATABASE_URL이 설정되어 있지 않습니다. "
            ".env 파일을 확인하거나 TEST_DATABASE_URL을 명시하세요."
        )

    # SQLAlchemy make_url: driver-aware (postgresql+psycopg2 등) + query string 보존
    # 주의: str(url)은 비밀번호를 '***'로 마스킹하므로 render_as_string(hide_password=False) 필수
    url = make_url(prod_url)
    return url.set(database="safeagent_test").render_as_string(hide_password=False)


_TEST_URL = _resolve_test_database_url()


# ── ③ 안전 가드: 운영 DB로의 실수 방지 (정확 매칭) ───────────────
# 파싱한 database 이름이 정확히 'safeagent_test'인지 확인
_parsed = make_url(_TEST_URL)
if _parsed.database != "safeagent_test":
    raise RuntimeError(
        f"테스트 DB 이름이 'safeagent_test'가 아닙니다.\n"
        f"  현재 database: {_parsed.database!r}\n"
        f"  현재 URL: {_parsed!r}\n"
        f"안전을 위해 테스트는 'safeagent_test' DB에서만 실행됩니다.\n"
        f"운영 DB와 격리된 테스트 DB를 사용하세요."
    )


# ── ④ DATABASE_URL을 테스트 URL로 덮어쓰기 ──────────────────────
# src.* 모듈이 import될 때 이 값을 보고 engine을 생성함
os.environ["DATABASE_URL"] = _TEST_URL
