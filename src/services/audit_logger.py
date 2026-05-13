import json
from sqlalchemy.orm import Session

from src.database.models import AuditLogModel
from src.schemas.audit import AuditLogCreate


class AuditLogger:
    def __init__(self, db: Session):
        self.db = db

    def log(self, log_data: AuditLogCreate) -> None:
        context_str = (
            json.dumps(log_data.context_json)
            if isinstance(log_data.context_json, dict)
            else str(log_data.context_json or {})
        )

        self.db.add(
            AuditLogModel(
                run_id=log_data.run_id,
                event_type=log_data.event_type,
                entity_type=log_data.entity_type,
                entity_id=log_data.entity_id,
                reason=log_data.reason,
                context_json=context_str,
            )
        )
        self.db.commit()


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
