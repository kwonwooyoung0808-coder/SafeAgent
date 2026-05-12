-- Phase 3-A: policy_versions + audit log policy_version 컬럼
-- 운영 DB(safeagent) 에 적용.

-- 1) policy_versions 테이블
CREATE TABLE IF NOT EXISTS policy_versions (
    id              VARCHAR(80) PRIMARY KEY,
    policy_id       VARCHAR(80) NOT NULL REFERENCES policies(id),
    version         VARCHAR(50) NOT NULL,
    yaml_path       VARCHAR(512) NOT NULL,
    yaml_snapshot   TEXT,
    is_current      BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    activated_at    TIMESTAMP,
    deactivated_at  TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_policy_versions_id
    ON policy_versions(id);

CREATE INDEX IF NOT EXISTS ix_policy_versions_policy_id
    ON policy_versions(policy_id);

CREATE INDEX IF NOT EXISTS ix_policy_versions_is_current
    ON policy_versions(is_current);

CREATE INDEX IF NOT EXISTS ix_policy_version_policy_current
    ON policy_versions(policy_id, is_current);

CREATE UNIQUE INDEX IF NOT EXISTS uq_policy_id_version
    ON policy_versions(policy_id, version);

-- 2) audit 테이블 3개에 policy_version 컬럼 추가
ALTER TABLE query_audit_logs    ADD COLUMN IF NOT EXISTS policy_version VARCHAR(50);
ALTER TABLE response_audit_logs ADD COLUMN IF NOT EXISTS policy_version VARCHAR(50);
ALTER TABLE violation_reports   ADD COLUMN IF NOT EXISTS policy_version VARCHAR(50);

-- 3) 기존 정책마다 첫 버전 row 자동 생성 (앱 재시작 시 seed 가 처리하지만,
--    운영 DB 에 미리 채워두면 첫 호출부터 audit 에 version 이 기록됨)
INSERT INTO policy_versions (id, policy_id, version, yaml_path, is_current, activated_at)
SELECT
    gen_random_uuid()::text,
    p.id,
    COALESCE(p.version, '1.0'),
    p.yaml_path,
    TRUE,
    NOW()
FROM policies p
WHERE NOT EXISTS (
    SELECT 1 FROM policy_versions pv
    WHERE pv.policy_id = p.id AND pv.is_current = TRUE
);

