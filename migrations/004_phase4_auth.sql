-- Phase 4: 인증/권한 테이블 (스키마 only)
-- 인증 방식: JWT (사람) + API Key (머신)  — NIST SP 800-228 REC-API-11
-- 권한 모델: Role 3종 (admin / operator / viewer)
-- policy_groups JSONB 컬럼은 Phase 2 부서 스코프 확장 대비.
--
-- 타입 결정 근거:
--   - id: VARCHAR(80) — 기존 agents/policies/violation_reports 등 전체 테이블과 통일
--                      (PRD §11 은 UUID 명시이나 실제 구현은 의미 있는 코드값
--                       (CONTENT_001 등)을 쓰기 위해 VARCHAR(80) 로 적응됨)
--   - JSONB: 001/002 기존 마이그레이션이 JSONB 사용 — 인덱싱/연산자 이점
--
-- 기본 admin 시드는 SQL 이 아닌 앱 lifespan 에서 처리 (bcrypt 해시는 코드로 생성).

-- ── users 테이블 ──────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id              VARCHAR(80)  PRIMARY KEY,
    username        VARCHAR(255) UNIQUE NOT NULL,
    hashed_password TEXT         NOT NULL,
    role            VARCHAR(20)  NOT NULL DEFAULT 'viewer'
                    CHECK (role IN ('admin', 'operator', 'viewer')),
    policy_groups   JSONB        NOT NULL DEFAULT '[]'::jsonb,
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMP    NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_users_username ON users(username);
CREATE INDEX IF NOT EXISTS ix_users_role     ON users(role);


-- ── api_keys 테이블 ───────────────────────────
-- Sovereign AI Agent → /v1/input-guard, /v1/response-guard, /v1/proxy 호출에 사용.
-- 실제 키는 저장하지 않고 SHA-256 해시만 보관.
CREATE TABLE IF NOT EXISTS api_keys (
    id            VARCHAR(80)  PRIMARY KEY,
    agent_id      VARCHAR(80)  NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    key_hash      VARCHAR(128) UNIQUE NOT NULL,
    description   VARCHAR(255),
    is_active     BOOLEAN      NOT NULL DEFAULT TRUE,
    expires_at    TIMESTAMP,
    created_at    TIMESTAMP    NOT NULL DEFAULT NOW(),
    last_used_at  TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_api_keys_agent_id ON api_keys(agent_id);
CREATE INDEX IF NOT EXISTS ix_api_keys_key_hash ON api_keys(key_hash);
