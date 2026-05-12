from typing import Literal

from pydantic import BaseModel, Field


class JudgeResult(BaseModel):
    verdict: Literal["PASS", "FAIL"]
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    evidence_text: str | None = None
    severity: str | None = None
    action: str | None = None

