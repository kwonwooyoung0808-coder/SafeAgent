"""
게이트웨이 라우터 공통 검증 헬퍼.

input_guard / response_guard / proxy 라우터가 공통으로 수행하던
agent / policy 활성 상태 검증을 한 곳에 모은다.

원칙: PRD §4.x의 422/500 응답 의미를 그대로 보존. 메시지 포맷도 변경 없음.
"""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from src.database.models import AgentModel, PolicyModel


def get_active_agent_or_422(db: Session, agent_id: str) -> AgentModel:
    """Agent가 존재하고 status=ACTIVE 면 반환, 아니면 422.

    PRD §4.1/§4.2/§4.4 의 'agent_id={id} 없음 또는 비활성' 메시지와 동일.
    """
    agent = db.query(AgentModel).filter(
        AgentModel.id == agent_id,
        AgentModel.status == "ACTIVE",
    ).first()
    if not agent:
        raise HTTPException(
            status_code=422,
            detail=f"agent_id={agent_id} 없음 또는 비활성",
        )
    return agent


def get_active_system_policy_or_500(db: Session, policy_id: str) -> PolicyModel:
    """시스템 입력 정책이 존재하고 활성이면 반환, 아니면 500.

    F1 input_guard 전용. SYSTEM_INPUT_POLICY_ID 운영자 설정 오류를 명확히 알리는 메시지.
    """
    policy = db.query(PolicyModel).filter(
        PolicyModel.id == policy_id,
        PolicyModel.is_active == True,
    ).first()
    if not policy:
        raise HTTPException(
            status_code=500,
            detail=(
                f"시스템 입력 정책 '{policy_id}' 미설정 또는 비활성. "
                f"관리자가 SYSTEM_INPUT_POLICY_ID 환경변수를 확인해야 합니다."
            ),
        )
    return policy


def validate_combined_policies_active(db: Session, policy_ids: list[str]) -> None:
    """결합 대상 정책 ID 들이 모두 활성 상태인지 검증. 누락/비활성 시 422.

    F2 response_guard / proxy 의 다중 정책 결합 흐름 공용.
    하나라도 빠지면 PRD §11.4 결합 의미가 무너지므로 즉시 거부.
    """
    for pid in policy_ids:
        exists = db.query(PolicyModel).filter(
            PolicyModel.id == pid,
            PolicyModel.is_active == True,
        ).first()
        if not exists:
            raise HTTPException(
                status_code=422,
                detail=f"policy_id={pid} 없음 또는 미활성 (결합 대상: {policy_ids})",
            )
