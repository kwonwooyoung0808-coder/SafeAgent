from functools import lru_cache
from typing import Any, TypedDict

from src.schemas.workflow import EvaluateRequest, WorkflowState
from src.workflows.interceptors.interceptor import evaluate_final_response
from src.workflows.state import apply_generated_response, build_initial_state

try:
    from langgraph.graph import END, START, StateGraph
except ImportError:  # pragma: no cover - optional dependency until langgraph is installed
    END = "END"
    START = "START"
    StateGraph = None


class WorkflowGraphState(TypedDict, total=False):
    run_id: str
    user_input: str
    requested_response: str | None
    generated_response: str | None
    final_response: str | None
    context: dict[str, Any]
    retrieved_context: list[str] | None
    policy_results: list[Any]
    judge_results: dict[str, Any]
    violations: list[Any]
    action: Any
    status: str
    error_message: str | None


def run_generator_step(state: WorkflowState) -> WorkflowState:
    generated_response = state.requested_response or f"Generated response for: {state.user_input}"
    return apply_generated_response(state, generated_response)


def run_governance_step(state: WorkflowState) -> WorkflowState:
    return evaluate_final_response(state)


def _generate_node(state: WorkflowGraphState) -> WorkflowGraphState:
    workflow_state = WorkflowState.model_validate(state)
    updated = run_generator_step(workflow_state)
    return {
        "generated_response": updated.generated_response,
        "final_response": updated.final_response,
        "status": updated.status,
    }


def _intercept_node(state: WorkflowGraphState) -> WorkflowGraphState:
    workflow_state = WorkflowState.model_validate(state)
    updated = run_governance_step(workflow_state)
    return {
        "policy_results": updated.policy_results,
        "judge_results": updated.judge_results,
        "violations": updated.violations,
        "action": updated.action,
        "final_response": updated.final_response,
        "status": updated.status,
        "error_message": updated.error_message,
    }


@lru_cache
def build_workflow_graph():
    if StateGraph is None:
        return None

    graph = StateGraph(WorkflowGraphState)
    graph.add_node("generate", _generate_node)
    graph.add_node("intercept", _intercept_node)
    graph.add_edge(START, "generate")
    graph.add_edge("generate", "intercept")
    graph.add_edge("intercept", END)
    return graph.compile()


def execute_workflow(request: EvaluateRequest) -> WorkflowState:
    initial_state = build_initial_state(request)
    graph = build_workflow_graph()

    if graph is None:
        state = run_generator_step(initial_state)
        state = run_governance_step(state)
        return state

    result = graph.invoke(initial_state.model_dump())
    return WorkflowState.model_validate(result)
