from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AuditLogCreate(BaseModel):
    run_id: str
    event_type: str
    entity_type: str
    entity_id: str | None = None
    reason: str
    context_json: dict | str


class AuditLogResponse(BaseModel):
    id: int
    run_id: str
    event_type: str
    entity_type: str
    entity_id: str | None
    reason: str
    context: dict[str, Any]
    created_at: datetime
