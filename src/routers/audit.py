import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.dependencies import get_db
from src.database.models import AuditLogModel, QueryAuditLogModel, ResponseAuditLogModel
from src.schemas.audit import AuditLogResponse # 스키마 임포트

router = APIRouter(prefix="/v1", tags=["audit"])

# response_model을 지정해 주어야 Swagger에 문서화됩니다.
@router.get("/audit-logs", response_model=list[AuditLogResponse])
def list_audit_logs(limit: int = 100, db: Session = Depends(get_db)):
    rows = list(db.scalars(select(AuditLogModel).order_by(AuditLogModel.created_at.desc()).limit(limit)))
    result = []
    for row in rows:
        # 안전한 JSON 파싱 처리
        try:
            parsed_context = json.loads(row.context_json) if row.context_json else {}
        except json.JSONDecodeError:
            parsed_context = {}

        result.append({
            "id": row.id,
            "run_id": row.run_id,
            "event_type": row.event_type,
            "entity_type": row.entity_type,
            "entity_id": row.entity_id,
            "reason": row.reason,
            "context": parsed_context,
            "created_at": row.created_at,
        })
    return result


# ──────────────────────────────────────────────────────────────
# PRD 9: GET /v1/audit/query/{audit_id} — Feature 1 감사 로그 조회
# ──────────────────────────────────────────────────────────────
query_audit_router = APIRouter(prefix="/v1/audit", tags=["audit"])


@query_audit_router.get("/query/{audit_id}")
def get_query_audit(audit_id: str, db: Session = Depends(get_db)) -> dict:
    """Feature 1 응답의 audit_id로 질의 감사 로그 단건 조회."""
    row = db.query(QueryAuditLogModel).filter(QueryAuditLogModel.id == audit_id).first()
    if not row:
        raise HTTPException(status_code=404, detail=f"audit_id={audit_id} 없음")

    return {
        "audit_id":     row.id,
        "trace_id":     row.trace_id,
        "agent_id":     row.agent_id,
        "policy_id":    row.policy_id,
        "policy_version": row.policy_version,
        "query":        row.query,
        "masked_query": row.masked_query,
        "pii_detected": row.pii_detected,
        "context":      row.context,
        "risk_score":   row.risk_score,
        "status":       row.status,
        "risk_reasons": row.risk_reasons,
        "action_taken": row.action_taken,
        "created_at":   row.created_at,
    }


@query_audit_router.get("/response/{audit_id}")
def get_response_audit(audit_id: str, db: Session = Depends(get_db)) -> dict:
    """Feature 2 응답의 audit_id로 응답 감사 로그 단건 조회."""
    row = db.query(ResponseAuditLogModel).filter(ResponseAuditLogModel.id == audit_id).first()
    if not row:
        raise HTTPException(status_code=404, detail=f"audit_id={audit_id} 없음")

    return {
        "audit_id":         row.id,
        "trace_id":         row.trace_id,
        "query_audit_id":   row.query_audit_id,
        "agent_id":         row.agent_id,
        "policy_id":        row.policy_id,
        "policy_version":   row.policy_version,
        "query":            row.query,
        "masked_query":     row.masked_query,
        "response":         row.response,
        "masked_response":  row.masked_response,
        "pii_detected":     row.pii_detected,
        "compliance_score": row.compliance_score,
        "status":           row.status,
        "violations":       row.violations,
        "created_at":       row.created_at,
    }