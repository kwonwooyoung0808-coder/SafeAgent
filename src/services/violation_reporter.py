"""Policy Violation Reporter (PRD §7).

F1 BLOCKED 또는 F2 REJECTED 가 발생할 때 violation_reports 테이블에 자동 기록.
관리자가 후속 조치할 수 있도록 사유, 원본 질의/응답, 심각도를 함께 보존한다.

이 모듈은 best-effort: DB 저장 실패가 사용자 응답을 막지 않도록 예외를 흡수.
"""
from __future__ import annotations

import logging
import uuid

from src.database.connection import SessionLocal
from src.database.models import ViolationReportModel
from src.utils.masker import mask_pii

logger = logging.getLogger(__name__)


def _summary_from(violations: list[dict] | None, risk_reasons: list[str] | None) -> str:
    if violations:
        first = violations[0]
        desc = first.get("description") or first.get("type") or "정책 위반"
        return str(desc)[:500]
    if risk_reasons:
        return str(risk_reasons[0])[:500]
    return "정책 위반"


def _primary_category(violations: list[dict] | None) -> str | None:
    if not violations:
        return None
    for v in violations:
        if (v.get("severity") or "").upper() == "HIGH":
            return v.get("type") or v.get("category")
    return violations[0].get("type") or violations[0].get("category")


def _highest_severity(violations: list[dict] | None) -> str:
    if not violations:
        return "HIGH"
    rank = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    sev = min(
        (v.get("severity", "LOW").upper() for v in violations),
        key=lambda s: rank.get(s, 3),
        default="HIGH",
    )
    return sev


def report_violation(
    *,
    stage: str,
    agent_id: str | None,
    trace_id: str | None = None,
    query_audit_id: str | None = None,
    response_audit_id: str | None = None,
    policy_version: str | None = None,
    original_query: str | None = None,
    original_response: str | None = None,
    violations: list[dict] | None = None,
    risk_reasons: list[str] | None = None,
) -> str | None:
    """위반 리포트를 INSERT 하고 생성된 report_id 를 반환. 실패 시 None."""
    report_id = str(uuid.uuid4())
    masked_q, _ = mask_pii(original_query)
    masked_r, _ = mask_pii(original_response)
    session = SessionLocal()
    try:
        session.add(ViolationReportModel(
            id=report_id,
            trace_id=trace_id,
            agent_id=agent_id,
            stage=stage,
            query_audit_id=query_audit_id,
            response_audit_id=response_audit_id,
            severity=_highest_severity(violations),
            primary_category=_primary_category(violations),
            policy_version=policy_version,
            summary=_summary_from(violations, risk_reasons),
            original_query=original_query,
            masked_query=masked_q,
            original_response=original_response,
            masked_response=masked_r,
            violations=violations or [],
            risk_reasons=risk_reasons or [],
            status="NEW",
        ))
        session.commit()
        return report_id
    except Exception as e:
        session.rollback()
        logger.warning("violation_report 저장 실패 (best-effort): %s", e)
        return None
    finally:
        session.close()
