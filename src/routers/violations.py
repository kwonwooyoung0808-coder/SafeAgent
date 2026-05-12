from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.dependencies import get_db
from src.database.models import EvidenceSpanModel, ViolationModel

router = APIRouter(prefix="/api/v1", tags=["violations"])


@router.get("/violations")
def list_violations(limit: int = 100, db: Session = Depends(get_db)):
    rows = list(db.scalars(select(ViolationModel).order_by(ViolationModel.created_at.desc()).limit(limit)))
    payload = []
    for row in rows:
        evidence = db.scalars(
            select(EvidenceSpanModel).where(EvidenceSpanModel.violation_id == row.violation_id)
        ).first()
        payload.append(
            {
                "id": row.violation_id,
                "run_id": row.run_id,
                "policy_id": row.policy_id,
                "policy_name": row.policy_name,
                "reason": row.reason,
                "source": row.source,
                "evidence_span": None
                if evidence is None
                else {
                    "text": evidence.text,
                    "start_char": evidence.start_char,
                    "end_char": evidence.end_char,
                    "source": evidence.source,
                    "condition": evidence.condition,
                    "policy_id": evidence.policy_id,
                    "confidence": evidence.confidence,
                    "human_reason": evidence.human_reason,
                },
                "recommended_action": row.recommended_action,
                "risk_score": row.risk_score,
                "judge_verdict": row.judge_verdict,
                "judge_confidence": row.judge_confidence,
                "created_at": row.created_at,
            }
        )
    return payload

