from src.schemas.action import ActionResult
from src.schemas.violation import Violation

FALLBACK_BLOCK_MESSAGE = "The response was blocked because it violated a policy."


class ActionEngine:
    def decide(self, run_id: str, response: str, violations: list[Violation]) -> ActionResult:
        should_block = any(violation.recommended_action == "BLOCK" for violation in violations)
        if should_block:
            return ActionResult(
                run_id=run_id,
                action_type="BLOCK",
                message=FALLBACK_BLOCK_MESSAGE,
                delivered_response=FALLBACK_BLOCK_MESSAGE,
            )
        should_flag = any(violation.recommended_action == "FLAGGED" for violation in violations)
        if should_flag:
            return ActionResult(
                run_id=run_id,
                action_type="FLAGGED",
                message="Response was flagged for review.",
                delivered_response=response,
            )
        return ActionResult(
            run_id=run_id,
            action_type="PASS" if not violations else "LOG",
            message="Response passed policy checks." if not violations else "Response was logged.",
            delivered_response=response,
        )
