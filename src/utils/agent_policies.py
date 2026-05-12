"""에이전트의 적용 정책 ID 목록 해석 (Phase 2-C).

F2 정책 결합 우선순위:
1. 시스템 입력 정책 (항상 첫 번째)
2. agent.policy_id (legacy 단일 정책 — 있으면)
3. agent 가 속한 모든 정책 그룹의 멤버 정책

중복은 자동 제거하되 순서는 우선순위대로 보존.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.database.models import (
    AgentModel,
    AgentPolicyGroupMappingModel,
    PolicyGroupMemberModel,
)


def resolve_agent_policy_ids(
    db: Session,
    *,
    agent: AgentModel,
    system_policy_id: str,
    request_policy_id: str | None = None,
) -> list[str]:
    """F2 가 적용해야 할 정책 ID 리스트를 우선순위 순으로 반환.

    Args:
        agent: 검증 대상 에이전트
        system_policy_id: 시스템 입력 정책 (항상 포함)
        request_policy_id: 요청에 명시된 정책 (있으면 agent.policy_id 보다 우선)

    Returns:
        중복 제거된 정책 ID 리스트. 시스템 정책이 항상 첫 번째.
    """
    ordered: list[str] = [system_policy_id]

    department_policy_id = request_policy_id or agent.policy_id
    if department_policy_id:
        ordered.append(department_policy_id)

    group_policy_rows = (
        db.query(PolicyGroupMemberModel.policy_id)
        .join(
            AgentPolicyGroupMappingModel,
            AgentPolicyGroupMappingModel.group_id == PolicyGroupMemberModel.group_id,
        )
        .filter(AgentPolicyGroupMappingModel.agent_id == agent.id)
        .all()
    )
    for (pid,) in group_policy_rows:
        ordered.append(pid)

    # 중복 제거 (순서 보존)
    seen: set[str] = set()
    unique: list[str] = []
    for pid in ordered:
        if pid not in seen:
            seen.add(pid)
            unique.append(pid)
    return unique
