from sqlalchemy.orm import Session

from src.database.models import ExecutionTraceModel

class TraceLogger:
    def __init__(self, db: Session):
        self.db = db

    def log_node(
        self,
        run_id: str,
        workflow_name: str,
        node_name: str,
        node_type: str,
        latency_ms: float = 0.0,
        status: str = "completed",
    ) -> None:
        self.db.add(
            ExecutionTraceModel(
                run_id=run_id,
                workflow_name=workflow_name,
                node_name=node_name,
                node_type=node_type,
                latency_ms=latency_ms,
                status=status,
            )
        )
        self.db.commit()
