from typing import Literal

from pydantic import BaseModel, Field


class EvidenceSpan(BaseModel):
    text: str
    start_char: int | None = None
    end_char: int | None = None
    source: Literal["rule", "judge", "fallback"]
    condition: str | None = None
    policy_id: str | None = None
    confidence: float | None = None
    human_reason: str | None = None


class Violation(BaseModel):
    id: str
    run_id: str
    policy_id: str
    policy_name: str
    reason: str
    source: Literal["rule", "judge"]
    recommended_action: Literal["BLOCK", "LOG", "FLAGGED"]
    risk_score: float = Field(ge=0.0, le=1.0)
    evidence_span: EvidenceSpan | None = None
    judge_verdict: str | None = None
    judge_confidence: float | None = None
