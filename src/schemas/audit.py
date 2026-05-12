from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel


class AuditLogCreate(BaseModel):
    run_id: str
    event_type: str
    entity_type: str
    entity_id: str | None = None
    reason: str
    context_json: dict | str


class AuditLogResponse(BaseModel):
    id: int
    run_id: str
    event_type: str
    entity_type: str
    entity_id: str | None
    reason: str
    context: dict[str, Any]
    created_at: datetime


class QueryAuditLogCreate(BaseModel):
    agent_id: str
    policy_id: str
    query: str
    context: str | None
    risk_score: float
    status: Literal["BLOCKED", "WARNED", "PASSED"]
    risk_reasons: list[str]
    action_taken: str


class QueryAuditLogResponse(BaseModel):
    id: str
    agent_id: str
    policy_id: str
    query: str
    risk_score: float
    status: str
    action_taken: str
    created_at: datetime


class ResponseAuditLogCreate(BaseModel):
    agent_id: str
    policy_id: str
    query: str
    response: str
    compliance_score: float
    status: Literal["APPROVED", "FLAGGED", "REJECTED"]
    violations: list[dict[str, Any]]
    audit_query_id: str | None = None


class ResponseAuditLogResponse(BaseModel):
    id: str
    agent_id: str
    compliance_score: float
    status: str
    violations: list[dict[str, Any]]
    created_at: datetime
