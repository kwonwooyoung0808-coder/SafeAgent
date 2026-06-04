-- Phase 4-B: Policy Compiler 성능 메트릭 컬럼 추가
-- 변환 실행 시간, LLM 호출 수, 청크 수, 환각 제거 수를 기록해
-- 병목 분석 및 품질 트래킹에 활용한다.

ALTER TABLE policy_conversion_logs
    ADD COLUMN IF NOT EXISTS total_latency_ms  INTEGER  DEFAULT 0;

ALTER TABLE policy_conversion_logs
    ADD COLUMN IF NOT EXISTS llm_call_count    INTEGER  DEFAULT 0;

ALTER TABLE policy_conversion_logs
    ADD COLUMN IF NOT EXISTS chunk_count       INTEGER  DEFAULT 0;

ALTER TABLE policy_conversion_logs
    ADD COLUMN IF NOT EXISTS hallucination_removals_count INTEGER DEFAULT 0;

COMMENT ON COLUMN policy_conversion_logs.total_latency_ms IS
    '전체 변환 파이프라인 실행 시간 (밀리초). 노드별 합산 값.';

COMMENT ON COLUMN policy_conversion_logs.llm_call_count IS
    'Step 1 + Step 2 + 금지어 전용 LLM 호출 횟수 합산.';

COMMENT ON COLUMN policy_conversion_logs.chunk_count IS
    '대형 문서 청킹 처리 시 분할된 청크 수. 소형 문서는 0.';

COMMENT ON COLUMN policy_conversion_logs.hallucination_removals_count IS
    'GroundingValidator가 제거한 환각 금지어 수.';

CREATE INDEX IF NOT EXISTS ix_policy_conversion_logs_latency
    ON policy_conversion_logs(total_latency_ms);

CREATE INDEX IF NOT EXISTS ix_policy_conversion_logs_status_latency
    ON policy_conversion_logs(conversion_status, total_latency_ms);
