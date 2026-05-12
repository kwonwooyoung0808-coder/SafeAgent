from src.schemas.judge import JudgeResult
from src.schemas.policy import Policy, PolicyEvaluationResult
from src.schemas.workflow import WorkflowState


def collect_judge_results(
    state: WorkflowState,
    policies: list[tuple[Policy, PolicyEvaluationResult]],
    judge_engine,
) -> dict[str, JudgeResult]:
    response = state.generated_response or state.final_response or ""
    results: dict[str, JudgeResult] = {}
    for policy, evaluation in policies:
        if evaluation.judge_required and not evaluation.triggered:
            results[policy.id] = judge_engine.judge(
                policy=policy,
                response=response,
                retrieved_context=state.retrieved_context,
            )
    return results
