-- Phase 2-C: Policy Groups + Agent ↔ Group 다대다 매핑
-- 운영 DB(safeagent) 에 신규 테이블 3개 생성.

-- 1) policy_groups
CREATE TABLE IF NOT EXISTS policy_groups (
    id          VARCHAR(80) PRIMARY KEY,
    name        VARCHAR(255) NOT NULL,
    description TEXT,
    created_at  TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMP NOT NULL DEFAULT NOW()
);

-- 2) policy_group_members (그룹 ↔ 정책 다대다)
CREATE TABLE IF NOT EXISTS policy_group_members (
    group_id   VARCHAR(80) NOT NULL REFERENCES policy_groups(id) ON DELETE CASCADE,
    policy_id  VARCHAR(80) NOT NULL REFERENCES policies(id),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (group_id, policy_id)
);

-- 3) agent_policy_group_mapping (에이전트 ↔ 그룹 다대다)
CREATE TABLE IF NOT EXISTS agent_policy_group_mapping (
    agent_id   VARCHAR(80) NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    group_id   VARCHAR(80) NOT NULL REFERENCES policy_groups(id) ON DELETE CASCADE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (agent_id, group_id)
);

