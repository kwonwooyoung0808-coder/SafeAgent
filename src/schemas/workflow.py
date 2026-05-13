from datetime import datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator

from src.schemas.action import ActionResult
from src.schemas.judge import JudgeResult
from src.schemas.policy import Policy, PolicyEvaluationResult
from src.schemas.violation import Violation

PolicyResultEntry = tuple[Policy, PolicyEvaluationResult]


class EvaluateRequest(BaseModel):
    run_id: str | None = None
    input: str
    response: str = Field(min_length=1, max_length=50000)
    context: dict[str, Any] = Field(default_factory=dict)
    retrieved_context: list[str] | None = None

    @model_validator(mode="after")
    def ensure_run_id(self) -> "EvaluateRequest":
        if not self.run_id:
            self.run_id = f"run_{uuid4().hex[:12]}"
        return self


class EvaluateResponse(BaseModel):
    run_id: str
    has_violation: bool
    final_action: Literal["BLOCK", "LOG", "PASS", "FLAGGED"]
    final_response: str
    violations: list[Violation] = Field(default_factory=list)


class TraceNodeRead(BaseModel):
    id: int
    run_id: str
    workflow_name: str
    node_name: str
    node_type: str
    latency_ms: float
    status: str
    created_at: datetime


class RunTraceSummary(BaseModel):
    run_id: str
    workflow_name: str
    status: str
    nodes: list[TraceNodeRead]
    created_at: datetime | None = None


class WorkflowState(BaseModel):
    run_id: str
    user_input: str
    requested_response: str | None = None
    generated_response: str | None = None
    final_response: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)
    retrieved_context: list[str] | None = None
    policy_results: list[PolicyResultEntry] = Field(default_factory=list)
    judge_results: dict[str, JudgeResult] = Field(default_factory=dict)
    violations: list[Violation] = Field(default_factory=list)
    action: ActionResult | None = None
    status: str = "running"
    error_message: str | None = None

class RunResponse(BaseModel):
    """GET /api/v1/runs/{run_id} API의 응답 규격 스키마"""
    run_id: str
    input: str
    output: str
    final_status: str
    final_action: str
    has_violation: bool
    workflow_name: str
    context: dict[str, Any]
    created_at: datetime
