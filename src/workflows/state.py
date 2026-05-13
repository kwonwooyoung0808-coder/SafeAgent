from src.schemas.action import ActionResult
from src.schemas.violation import Violation
from src.schemas.workflow import EvaluateRequest, PolicyResultEntry, WorkflowState
from src.schemas.judge import JudgeResult


def build_initial_state(request: EvaluateRequest) -> WorkflowState:
    return WorkflowState(
        run_id=request.run_id,
        user_input=request.input,
        requested_response=request.response,
        context=request.context,
        retrieved_context=request.retrieved_context,
    )


def apply_generated_response(state: WorkflowState, response: str) -> WorkflowState:
    state.generated_response = response
    state.final_response = response
    return state


def apply_policy_results(state: WorkflowState, policy_results: list[PolicyResultEntry]) -> WorkflowState:
    state.policy_results = policy_results
    return state


def apply_judge_results(state: WorkflowState, judge_results: dict[str, JudgeResult]) -> WorkflowState:
    state.judge_results = judge_results
    return state


def apply_violations(state: WorkflowState, violations: list[Violation]) -> WorkflowState:
    state.violations = violations
    return state


def apply_action(state: WorkflowState, action: ActionResult) -> WorkflowState:
    state.action = action
    state.final_response = action.delivered_response
    state.status = "completed"
    return state


__all__ = [
    "WorkflowState",
    "build_initial_state",
    "apply_generated_response",
    "apply_policy_results",
    "apply_judge_results",
    "apply_violations",
    "apply_action",
]
