from datetime import date, datetime, timezone

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.database.connection import Base


class WorkflowRunModel(Base):
    __tablename__ = "workflow_runs"

    run_id: Mapped[str] = mapped_column(String(80), primary_key=True, index=True)
    input: Mapped[str] = mapped_column(Text)
    output: Mapped[str] = mapped_column(Text)
    final_status: Mapped[str] = mapped_column(String(40), default="completed")
    final_action: Mapped[str] = mapped_column(String(20), default="LOG")
    has_violation: Mapped[bool] = mapped_column(Boolean, default=False)
    workflow_name: Mapped[str] = mapped_column(String(120), default="governance_workflow")
    context_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class ViolationModel(Base):
    __tablename__ = "violations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    violation_id: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    run_id: Mapped[str] = mapped_column(String(80), index=True)
    policy_id: Mapped[str] = mapped_column(String(80), index=True)
    policy_name: Mapped[str] = mapped_column(String(120))
    reason: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(20))
    risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    recommended_action: Mapped[str] = mapped_column(String(20))
    judge_verdict: Mapped[str | None] = mapped_column(String(20), nullable=True)
    judge_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class EvidenceSpanModel(Base):
    __tablename__ = "evidence_spans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    violation_id: Mapped[str] = mapped_column(String(80), ForeignKey("violations.violation_id"), index=True)
    text: Mapped[str] = mapped_column(Text)
    start_char: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_char: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[str] = mapped_column(String(20))
    condition: Mapped[str | None] = mapped_column(String(80), nullable=True)
    policy_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    human_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

class AuditLogModel(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(80), index=True)
    event_type: Mapped[str] = mapped_column(String(80))
    entity_type: Mapped[str] = mapped_column(String(80))
    entity_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    reason: Mapped[str] = mapped_column(Text)
    context_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class ExecutionTraceModel(Base):
    __tablename__ = "execution_traces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(80), index=True)
    workflow_name: Mapped[str] = mapped_column(String(120))
    node_name: Mapped[str] = mapped_column(String(120))
    node_type: Mapped[str] = mapped_column(String(80))
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(40), default="completed")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


# ──────────────────────────────────────────────────────────────
# PRD 8.1 신규 테이블 — Feature 1/2/3 전용 (기존 테이블과 독립)
# ──────────────────────────────────────────────────────────────


class AgentModel(Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(80), primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    policy_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("policies.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class PolicyModel(Base):
    __tablename__ = "policies"

    id: Mapped[str] = mapped_column(String(80), primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    version: Mapped[str] = mapped_column(String(50), default="1.0")
    yaml_path: Mapped[str] = mapped_column(String(512))
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    original_docx_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class QueryAuditLogModel(Base):
    __tablename__ = "query_audit_logs"

    id: Mapped[str] = mapped_column(String(80), primary_key=True, index=True)
    # PRD §6: 한 사용자 요청을 F1→F2→violation_report 까지 추적할 수 있는 체인 ID
    trace_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    agent_id: Mapped[str] = mapped_column(String(80), ForeignKey("agents.id"), index=True)
    policy_id: Mapped[str] = mapped_column(String(80), ForeignKey("policies.id"), index=True)
    # Phase 3-A: 어느 버전의 정책으로 평가되었는지 (사후 감사용)
    policy_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    query: Mapped[str] = mapped_column(Text)
    # PRD §6: PII 마스킹 사본 — 운영자/감사자에게 우선 노출됨. 원본은 query 컬럼 보존.
    masked_query: Mapped[str | None] = mapped_column(Text, nullable=True)
    pii_detected: Mapped[list | None] = mapped_column(JSON, nullable=True)
    context: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(50))
    risk_reasons: Mapped[list | None] = mapped_column(JSON, nullable=True)
    action_taken: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    # GET /api/agents/{id}/audit 쿼리 최적화: agent_id 필터 + created_at DESC 정렬
    __table_args__ = (
        Index("ix_query_audit_agent_created", "agent_id", "created_at"),
    )


class ResponseAuditLogModel(Base):
    __tablename__ = "response_audit_logs"

    id: Mapped[str] = mapped_column(String(80), primary_key=True, index=True)
    trace_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    query_audit_id: Mapped[str | None] = mapped_column(
        String(80), ForeignKey("query_audit_logs.id"), nullable=True, index=True
    )
    agent_id: Mapped[str] = mapped_column(String(80), ForeignKey("agents.id"), index=True)
    policy_id: Mapped[str] = mapped_column(String(80), ForeignKey("policies.id"), index=True)
    policy_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    query: Mapped[str] = mapped_column(Text)
    masked_query: Mapped[str | None] = mapped_column(Text, nullable=True)
    response: Mapped[str] = mapped_column(Text)
    masked_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    pii_detected: Mapped[list | None] = mapped_column(JSON, nullable=True)
    compliance_score: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(50))
    violations: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_response_audit_agent_created", "agent_id", "created_at"),
    )


class InquiryModel(Base):
    __tablename__ = "inquiries"

    id: Mapped[str] = mapped_column(String(80), primary_key=True, index=True)
    agent_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("agents.id"), nullable=True, index=True)
    user_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    inquiry_type: Mapped[str] = mapped_column(String(50))  # BLOCK_APPEAL / POLICY_QUESTION / OTHER
    audit_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    content: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="PENDING")  # PENDING / RESOLVED
    admin_reply: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_inquiry_user_created", "user_id", "created_at"),
    )


class PolicyGroupModel(Base):
    """정책 그룹 — 부서/팀 단위 정책 묶음 (PRD §X 다대다 매핑)."""
    __tablename__ = "policy_groups"

    id: Mapped[str] = mapped_column(String(80), primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class PolicyGroupMemberModel(Base):
    """정책 그룹 ↔ 정책 다대다 (그룹 1개에 여러 정책)."""
    __tablename__ = "policy_group_members"

    group_id: Mapped[str] = mapped_column(
        String(80), ForeignKey("policy_groups.id", ondelete="CASCADE"), primary_key=True
    )
    policy_id: Mapped[str] = mapped_column(
        String(80), ForeignKey("policies.id"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class AgentPolicyGroupMappingModel(Base):
    """에이전트 ↔ 정책 그룹 다대다 (에이전트가 여러 그룹 소속 가능)."""
    __tablename__ = "agent_policy_group_mapping"

    agent_id: Mapped[str] = mapped_column(
        String(80), ForeignKey("agents.id", ondelete="CASCADE"), primary_key=True
    )
    group_id: Mapped[str] = mapped_column(
        String(80), ForeignKey("policy_groups.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class ViolationReportModel(Base):
    """PRD §7 Policy Violation Reporter — 차단/거부된 사례를 자동 리포트.

    F1 BLOCKED 또는 F2 REJECTED 발생 시 자동 INSERT.
    관리자는 GET /v1/violation-reports 로 조회, PUT 으로 status 갱신.
    audit log 와 별도 테이블 — 관리자가 검토/조치할 워크큐 역할.
    """
    __tablename__ = "violation_reports"

    id: Mapped[str] = mapped_column(String(80), primary_key=True, index=True)
    trace_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    agent_id: Mapped[str | None] = mapped_column(
        String(80), ForeignKey("agents.id"), nullable=True, index=True
    )
    # 어느 단계에서 발생했는지: F1_QUERY (질의 차단) | F2_RESPONSE (응답 거부)
    stage: Mapped[str] = mapped_column(String(20), index=True)
    query_audit_id: Mapped[str | None] = mapped_column(
        String(80), ForeignKey("query_audit_logs.id"), nullable=True, index=True
    )
    response_audit_id: Mapped[str | None] = mapped_column(
        String(80), ForeignKey("response_audit_logs.id"), nullable=True, index=True
    )
    severity: Mapped[str] = mapped_column(String(20), default="HIGH")
    primary_category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    policy_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    summary: Mapped[str] = mapped_column(Text)
    original_query: Mapped[str | None] = mapped_column(Text, nullable=True)
    masked_query: Mapped[str | None] = mapped_column(Text, nullable=True)
    original_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    masked_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    violations: Mapped[list | None] = mapped_column(JSON, nullable=True)
    risk_reasons: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # NEW(접수) / REVIEWING(검토중) / RESOLVED(조치완료) / DISMISSED(반려)
    status: Mapped[str] = mapped_column(String(20), default="NEW", index=True)
    admin_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_violation_report_status_created", "status", "created_at"),
    )


class PolicyVersionModel(Base):
    """정책 버전 이력 (Phase 3-A).

    한 policy_id 에 여러 행 존재. is_current=TRUE 인 행이 활성 버전 (정확히 1개).
    yaml_snapshot 은 그 시점 YAML 전문을 보존해 파일 변경/삭제로부터 감사를 보호한다.
    """
    __tablename__ = "policy_versions"

    id: Mapped[str] = mapped_column(String(80), primary_key=True, index=True)
    policy_id: Mapped[str] = mapped_column(
        String(80), ForeignKey("policies.id"), index=True
    )
    version: Mapped[str] = mapped_column(String(50))
    yaml_path: Mapped[str] = mapped_column(String(512))
    yaml_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    activated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_policy_version_policy_current", "policy_id", "is_current"),
        Index("uq_policy_id_version", "policy_id", "version", unique=True),
    )


class UserModel(Base):
    """Phase 4: 인증 — 관리/조회 권한자 (admin / operator / viewer).

    JWT 발급 대상. policy_groups 는 Phase 2 부서 스코프 확장 대비.
    """
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(80), primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(20), default="viewer", index=True)
    policy_groups: Mapped[list] = mapped_column(JSON, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class ApiKeyModel(Base):
    """Phase 4: 인증 — Sovereign AI Agent (머신) 가 게이트웨이 호출에 사용.

    실제 키는 저장하지 않고 SHA-256 해시만 보관. 분실 시 재발급.
    """
    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(String(80), primary_key=True, index=True)
    agent_id: Mapped[str] = mapped_column(
        String(80), ForeignKey("agents.id", ondelete="CASCADE"), index=True
    )
    key_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class PolicyConversionLogModel(Base):
    __tablename__ = "policy_conversion_logs"

    id: Mapped[str] = mapped_column(String(80), primary_key=True, index=True)
    # 실패 케이스에는 policy_id 가 없을 수 있음 (정책 미생성).
    # 추적용 fail-marker 는 fail_marker 컬럼에 별도 저장.
    policy_id: Mapped[str | None] = mapped_column(
        String(80), ForeignKey("policies.id"), nullable=True, index=True
    )
    fail_marker: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    original_filename: Mapped[str] = mapped_column(String(512))
    parsed_rules_count: Mapped[int] = mapped_column(Integer, default=0)
    conversion_status: Mapped[str] = mapped_column(String(50))
    warnings: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
