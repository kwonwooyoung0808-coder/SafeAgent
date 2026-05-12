"""Policy Violation Reports 관리자 API (PRD §7)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.core.dependencies import get_db
from src.database.models import ViolationReportModel

router = APIRouter(prefix="/v1/violation-reports", tags=["violation-reports"])

ReportStatus = Literal["NEW", "REVIEWING", "RESOLVED", "DISMISSED"]


class ViolationReportItem(BaseModel):
    id: str
    trace_id: str | None
    agent_id: str | None
    stage: str
    query_audit_id: str | None
    response_audit_id: str | None
    severity: str
    primary_category: str | None
    policy_version: str | None
    summary: str
    original_query: str | None
    masked_query: str | None
    original_response: str | None
    masked_response: str | None
    violations: list[dict] = Field(default_factory=list)
    risk_reasons: list[str] = Field(default_factory=list)
    status: str
    admin_note: str | None
    created_at: datetime
    resolved_at: datetime | None


class ViolationReportListResponse(BaseModel):
    items: list[ViolationReportItem]
    total: int


class StatusUpdateRequest(BaseModel):
    status: ReportStatus
    admin_note: str | None = None


def _to_item(r: ViolationReportModel) -> ViolationReportItem:
    return ViolationReportItem(
        id=r.id,
        trace_id=r.trace_id,
        agent_id=r.agent_id,
        stage=r.stage,
        query_audit_id=r.query_audit_id,
        response_audit_id=r.response_audit_id,
        severity=r.severity,
        primary_category=r.primary_category,
        policy_version=r.policy_version,
        summary=r.summary,
        original_query=r.original_query,
        masked_query=r.masked_query,
        original_response=r.original_response,
        masked_response=r.masked_response,
        violations=r.violations or [],
        risk_reasons=r.risk_reasons or [],
        status=r.status,
        admin_note=r.admin_note,
        created_at=r.created_at,
        resolved_at=r.resolved_at,
    )


@router.get("", response_model=ViolationReportListResponse)
def list_reports(
    status: ReportStatus | None = Query(default=None),
    agent_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> ViolationReportListResponse:
    """위반 리포트 목록. 상태/agent 필터 + 페이지네이션."""
    q = db.query(ViolationReportModel)
    if status:
        q = q.filter(ViolationReportModel.status == status)
    if agent_id:
        q = q.filter(ViolationReportModel.agent_id == agent_id)
    total = q.count()
    rows = (
        q.order_by(ViolationReportModel.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    items = [_to_item(r) for r in rows]
    return ViolationReportListResponse(items=items, total=total)


@router.get("/{report_id}", response_model=ViolationReportItem)
def get_report(report_id: str, db: Session = Depends(get_db)) -> ViolationReportItem:
    r = db.query(ViolationReportModel).filter(ViolationReportModel.id == report_id).first()
    if not r:
        raise HTTPException(status_code=404, detail=f"report_id={report_id} 없음")
    return _to_item(r)


@router.put("/{report_id}/status", response_model=ViolationReportItem)
def update_status(
    report_id: str,
    payload: StatusUpdateRequest,
    db: Session = Depends(get_db),
) -> ViolationReportItem:
    r = db.query(ViolationReportModel).filter(ViolationReportModel.id == report_id).first()
    if not r:
        raise HTTPException(status_code=404, detail=f"report_id={report_id} 없음")

    r.status = payload.status
    if payload.admin_note is not None:
        r.admin_note = payload.admin_note
    if payload.status in ("RESOLVED", "DISMISSED") and r.resolved_at is None:
        r.resolved_at = datetime.now(timezone.utc)
    elif payload.status in ("NEW", "REVIEWING"):
        r.resolved_at = None

    db.commit()
    db.refresh(r)
    return _to_item(r)
