-- Phase 2-A: trace_id
ALTER TABLE query_audit_logs    ADD COLUMN IF NOT EXISTS trace_id VARCHAR(80);
ALTER TABLE response_audit_logs ADD COLUMN IF NOT EXISTS trace_id VARCHAR(80);
ALTER TABLE violation_reports   ADD COLUMN IF NOT EXISTS trace_id VARCHAR(80);

CREATE INDEX IF NOT EXISTS ix_query_audit_logs_trace_id    ON query_audit_logs(trace_id);
CREATE INDEX IF NOT EXISTS ix_response_audit_logs_trace_id ON response_audit_logs(trace_id);
CREATE INDEX IF NOT EXISTS ix_violation_reports_trace_id   ON violation_reports(trace_id);

-- Phase 2-B: PII masking
ALTER TABLE query_audit_logs    ADD COLUMN IF NOT EXISTS masked_query    TEXT;
ALTER TABLE query_audit_logs    ADD COLUMN IF NOT EXISTS pii_detected    JSONB;
ALTER TABLE response_audit_logs ADD COLUMN IF NOT EXISTS masked_query    TEXT;
ALTER TABLE response_audit_logs ADD COLUMN IF NOT EXISTS masked_response TEXT;
ALTER TABLE response_audit_logs ADD COLUMN IF NOT EXISTS pii_detected    JSONB;
ALTER TABLE violation_reports   ADD COLUMN IF NOT EXISTS masked_query    TEXT;
ALTER TABLE violation_reports   ADD COLUMN IF NOT EXISTS masked_response TEXT;
