from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class AgentCreate(BaseModel):
    """PRD 9: POST /api/agents 요청 스키마."""

    id: str | None = Field(
        default=None,
        description="에이전트 고유 ID. 미지정 시 서버가 'agent-{uuid8}' 형식으로 생성.",
    )
    name: str
    description: str | None = None
    policy_id: str | None = Field(
        default=None, description="연결할 활성 정책 ID. 미지정 시 추후 PUT으로 연결."
    )
    department_group_id: str | None = Field(
        default=None,
        description="Agent department policy group ID. The group is assigned on create.",
    )
    policy_group_ids: list[str] = Field(
        default_factory=list,
        description="Additional policy group IDs assigned on create.",
    )
    status: Literal["ACTIVE", "INACTIVE"] = "ACTIVE"


class AgentResponse(BaseModel):
    """PRD 9: GET /api/agents/{agent_id} 응답 스키마."""

    id: str
    name: str
    description: str | None = None
    policy_id: str | None = None
    policy_group_ids: list[str] = Field(default_factory=list)
    status: str
    created_at: datetime
    updated_at: datetime


class AgentPolicyUpdate(BaseModel):
    """PRD 9: PUT /api/agents/{agent_id}/policy 요청 스키마."""

    policy_id: str
