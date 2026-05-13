-- Phase 3-B: Policy Compiler review/trace safety
-- Adds requested policy id tracking for failed conversions.

ALTER TABLE policy_conversion_logs
    ADD COLUMN IF NOT EXISTS requested_policy_id VARCHAR(80);

CREATE INDEX IF NOT EXISTS ix_policy_conversion_logs_requested_policy_id
    ON policy_conversion_logs(requested_policy_id);
