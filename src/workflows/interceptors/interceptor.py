from src.core.config import get_settings
from src.engines.action_engine import ActionEngine
from src.engines.judge_engine import JudgeEngine
from src.engines.policy_engine import PolicyEngine
from src.engines.violation_engine import ViolationEngine
from src.schemas.workflow import WorkflowState
from src.workflows.interceptors.handlers.action_handler import build_action_result
from src.workflows.interceptors.handlers.judge_handler import collect_judge_results
from src.workflows.interceptors.handlers.policy_handler import collect_policy_results
from src.workflows.state import (
    apply_action,
    apply_judge_results,
    apply_policy_results,
    apply_violations,
)

def run_policy_stage(state: WorkflowState) -> WorkflowState:
    settings = get_settings()
    policy_results = collect_policy_results(
        state=state,
        policy_engine=PolicyEngine(),
        policy_dir=settings.policy_dir,
    )
    return apply_policy_results(state, policy_results)


def run_judge_stage(state: WorkflowState) -> WorkflowState:
    settings = get_settings()
    judge_results = collect_judge_results(
        state=state,
        policies=state.policy_results,
        judge_engine=JudgeEngine(settings.prompt_dir),
    )
    return apply_judge_results(state, judge_results)


def run_violation_stage(state: WorkflowState) -> WorkflowState:
    violation_engine = ViolationEngine()
    violations = []
    response = state.generated_response or state.final_response or ""
    for policy, result in state.policy_results:
        violation = violation_engine.from_policy_result(
            run_id=state.run_id,
            policy=policy,
            result=result,
            judge_result=state.judge_results.get(policy.id),
            response=response,
        )
        if violation:
            violations.append(violation)
    return apply_violations(state, violations)


def run_action_stage(state: WorkflowState) -> WorkflowState:
    response = state.generated_response or state.final_response or ""
    action = build_action_result(
        run_id=state.run_id,
        response=response,
        violations=state.violations,
        action_engine=ActionEngine(),
    )
    return apply_action(state, action)


def evaluate_final_response(state: WorkflowState) -> WorkflowState:
    state = run_policy_stage(state)
    state = run_judge_stage(state)
    state = run_violation_stage(state)
    state = run_action_stage(state)
    return state
