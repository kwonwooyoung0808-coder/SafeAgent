"""migrations/ 폴더의 .sql 을 번호 순으로 일괄 실행.

사용:
    .venv/Scripts/python.exe -m scripts.run_migrations

각 SQL 은 멱등 (IF NOT EXISTS) 이므로 여러 번 실행해도 안전.
실행 결과 (성공/실패) 를 stdout 에 출력.
"""
from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import create_engine, text

from src.core.config import get_settings


def main() -> int:
    settings = get_settings()
    engine = create_engine(settings.database_url)

    migrations_dir = Path(__file__).parent.parent / "migrations"
    if not migrations_dir.exists():
        print(f"ERROR: migrations 폴더 없음: {migrations_dir}")
        return 1

    sql_files = sorted(migrations_dir.glob("*.sql"))
    if not sql_files:
        print(f"ERROR: {migrations_dir} 에 .sql 파일 없음")
        return 1

    print(f"DB: {engine.url}")
    print(f"마이그레이션 {len(sql_files)} 개 발견")
    print()

    for sql_path in sql_files:
        print(f"[{sql_path.name}] 실행 중...")
        sql_text = sql_path.read_text(encoding="utf-8")
        try:
            with engine.begin() as conn:
                conn.execute(text(sql_text))
            print(f"[{sql_path.name}] OK")
        except Exception as e:
            print(f"[{sql_path.name}] FAILED: {type(e).__name__}: {e}")
            return 1
        print()

    print("모든 마이그레이션 완료.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
