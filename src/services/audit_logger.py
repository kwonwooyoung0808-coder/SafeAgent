import json
from sqlalchemy.orm import Session

from src.database.models import AuditLogModel, WorkflowRunModel
from src.schemas.workflow import EvaluateRequest
from src.schemas.audit import AuditLogCreate  #[추가] 상자(스키마) 형태로 가져옴.

class AuditLogger:
    def __init__(self, db: Session):
        self.db = db

    # 기존 evaluate.py 와의 호환성을 위한 범용 log 메서드
    def log(self, log_data: AuditLogCreate) -> None:
        # evaluate.py가 'context_json'이라는 이름으로 넘긴 데이터를 안전하게 문자열로 변환
        context_str = json.dumps(log_data.context_json) if isinstance(log_data.context_json, dict) else str(log_data.context_json or {})

        self.db.add(
            AuditLogModel(
                run_id=log_data.run_id,
                event_type=log_data.event_type,
                entity_type=log_data.entity_type,
                entity_id=log_data.entity_id,  # <- 팀원 코드가 보내는 entity_id 완벽 수용!
                reason=log_data.reason,
                context_json=context_str,      # <- 문자열로 예쁘게 변환된 데이터 삽입!
            )
        )
        self.db.commit()

    # 우리가 새로 만들었던 구체적인 로깅 메서드들 (유지)
    def log_policy_evaluation(self, run_id: str, has_violation: bool, context: dict) -> None:
        context_data = json.dumps(context) if isinstance(context, dict) else str(context)
        self.db.add(
            AuditLogModel(
                run_id=run_id,
                event_type="policy_evaluation",
                entity_type="run",
                reason="Violation detected." if has_violation else "No violation detected.",
                context_json=context_data,
            )
        )
        self.db.commit()

    def log_run_summary(self, request: EvaluateRequest, final_output: str, final_action: str) -> None:
        context_data = json.dumps(request.context) if isinstance(request.context, dict) else str(request.context)
        self.db.add(
            WorkflowRunModel(
                run_id=request.run_id,
                input=request.input,
                output=final_output,
                final_action=final_action,
                has_violation=(final_action == "BLOCK"),
                workflow_name="governance_workflow",
                context_json=context_data,
            )
        )
        self.db.commit()