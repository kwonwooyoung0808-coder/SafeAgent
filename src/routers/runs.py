import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from src.core.dependencies import get_db
from src.database.models import ExecutionTraceModel, WorkflowRunModel
# 추가된 RunResponse 스키마를 임포트합니다.
from src.schemas.workflow import RunResponse, RunTraceSummary, TraceNodeRead

router = APIRouter(prefix="/api/v1/runs", tags=["runs"])

# 1. response_model=RunResponse를 추가하여 Swagger(API 문서)에 응답 규격이 보이도록 합니다.
@router.get("/{run_id}", response_model=RunResponse)
def get_run(run_id: str, db: Session = Depends(get_db)):
    run = db.get(WorkflowRunModel, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found.")
    
    # 2. JSON 문자열이 깨져있거나 비어있을 때 서버가 죽지 않도록 방어(try-except)합니다.
    try:
        parsed_context = json.loads(run.context_json) if run.context_json else {}
    except json.JSONDecodeError:
        parsed_context = {}

    return {
        "run_id": run.run_id,
        "input": run.input,
        "output": run.output,
        "final_status": run.final_status,
        "final_action": run.final_action,
        "has_violation": run.has_violation,
        "workflow_name": run.workflow_name,
        "context": parsed_context,  # 안전하게 파싱된 딕셔너리를 넣습니다.
        "created_at": run.created_at,
    }


# Trace 조회 API는 이미 완벽하게 작성되어 있으므로 그대로 둡니다.
@router.get("/{run_id}/trace", response_model=RunTraceSummary)
def get_trace(run_id: str, db: Session = Depends(get_db)) -> RunTraceSummary:
    run = db.get(WorkflowRunModel, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found.")
    
    nodes = list(
        db.scalars(
            select(ExecutionTraceModel)
            .where(ExecutionTraceModel.run_id == run_id)
            .order_by(ExecutionTraceModel.id)
        )
    )
    
    return RunTraceSummary(
        run_id=run_id,
        workflow_name=run.workflow_name,
        status=run.final_status,
        nodes=[TraceNodeRead.model_validate(node, from_attributes=True) for node in nodes],
        created_at=run.created_at,
    )