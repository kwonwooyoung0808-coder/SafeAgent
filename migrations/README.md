# DB 마이그레이션

운영 DB(`safeagent`)에 신규 테이블/컬럼을 적용하는 SQL 모음.

> 테스트 DB(`safeagent_test`)는 매 테스트마다 `Base.metadata.create_all()`로 자동 재생성되므로 마이그레이션 필요 없음. 운영 DB만 수동 적용.

## 파일 순서

| # | 파일 | 내용 |
|---|------|------|
| 001 | `001_phase2_trace_id_and_masking.sql` | `trace_id`, `masked_query`, `masked_response`, `pii_detected` 컬럼 추가 |
| 002 | `002_phase2c_policy_groups.sql` | `policy_groups`, `policy_group_members`, `agent_policy_group_mapping` 테이블 생성 |
| 003 | `003_phase3a_policy_versions.sql` | `policy_versions` 테이블 + `policy_version` 컬럼 + 기존 정책 v1 시드 |

각 SQL 은 `IF NOT EXISTS` / `ADD COLUMN IF NOT EXISTS` 사용으로 **멱등** — 여러 번 실행해도 안전.

## 적용 방법

### 옵션 A — psql 직접 실행 (권장)

```cmd
set PGPASSWORD=a1234
"C:\Program Files\PostgreSQL\18\bin\psql.exe" -h localhost -p 5433 -U postgres -d safeagent -f migrations/001_phase2_trace_id_and_masking.sql
"C:\Program Files\PostgreSQL\18\bin\psql.exe" -h localhost -p 5433 -U postgres -d safeagent -f migrations/002_phase2c_policy_groups.sql
"C:\Program Files\PostgreSQL\18\bin\psql.exe" -h localhost -p 5433 -U postgres -d safeagent -f migrations/003_phase3a_policy_versions.sql
```

성공 시 각 파일마다 `ALTER TABLE` / `CREATE TABLE` / `CREATE INDEX` 메시지 출력.

### 옵션 B — Python 헬퍼 스크립트

```cmd
.venv\Scripts\python.exe -m scripts.run_migrations
```

내부적으로 `migrations/` 의 SQL 파일을 번호 순으로 읽어 실행.

## 적용 결과 검증

```sql
-- 컬럼 추가 확인
SELECT column_name FROM information_schema.columns
WHERE table_name = 'query_audit_logs' AND column_name IN ('trace_id', 'masked_query', 'pii_detected', 'policy_version');

-- 테이블 생성 확인
SELECT table_name FROM information_schema.tables
WHERE table_name IN ('policy_groups', 'policy_group_members', 'agent_policy_group_mapping', 'policy_versions');

-- 정책 버전 시드 확인
SELECT policy_id, version, is_current FROM policy_versions ORDER BY policy_id;
```

## 신규 환경 배포

새 회사/환경에 처음 배포 시:

1. PostgreSQL 18 설치 + `safeagent` DB 생성
2. 백엔드 1회 실행 → `init_db()` 가 `Base.metadata.create_all()` 로 모든 기본 테이블 생성
3. 위 마이그레이션 1-3 순서로 실행

신규 환경은 `init_db()` 만으로도 모든 테이블 + 컬럼이 생성되므로 마이그레이션 SQL은 **이미 운영 중인 DB 의 점진적 업데이트 용도** 입니다.
