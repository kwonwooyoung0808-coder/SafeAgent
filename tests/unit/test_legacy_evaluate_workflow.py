import pytest
from pydantic import ValidationError

from src.schemas.workflow import EvaluateRequest
from src.workflows.agent_workflow import run_generator_step
from src.workflows.state import build_initial_state


def test_evaluate_request_requires_response() -> None:
    with pytest.raises(ValidationError):
        EvaluateRequest(input="review this answer")


def test_generator_uses_provided_response_only() -> None:
    request = EvaluateRequest(
        input="review this answer",
        response="This is the response to evaluate.",
    )

    state = run_generator_step(build_initial_state(request))

    assert state.generated_response == "This is the response to evaluate."
    assert state.final_response == "This is the response to evaluate."
