def build_action_result(run_id: str, response: str, violations: list, action_engine):
    return action_engine.decide(run_id=run_id, response=response, violations=violations)

