import time
from contextlib import contextmanager
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

    # 우리가 추가했던 마법의 자동 타이머 기능!
    @contextmanager
    def measure_node(self, run_id: str, node_name: str, node_type: str, workflow_name: str = "governance_workflow"):
        start_time = time.perf_counter()
        status = "completed"
        try:
            yield
        except Exception:
            status = "failed"
            raise
        finally:
            end_time = time.perf_counter()
            latency_ms = round((end_time - start_time) * 1000, 2)
            self.log_node(
                run_id=run_id,
                workflow_name=workflow_name,
                node_name=node_name,
                node_type=node_type,
                latency_ms=latency_ms,
                status=status
            )