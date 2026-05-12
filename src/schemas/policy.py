from typing import Any, Literal, Optional
from pydantic import BaseModel, Field

class PolicyRule(BaseModel):
    """개별 룰(Rule)의 조건을 정의하는 스키마"""
    condition: str
    # 위반 탐지 시 후속 행동.
    # block_immediately: 즉시 차단 (고속 처리)
    # judge_fallback: 위반은 탐지했으나 문맥 파악을 위해 Judge(LLM)에게 2차 판단 위임
    on_rule_failure: Optional[Literal["block_immediately", "judge_fallback"]] = None
    parameters: dict[str, Any] = Field(default_factory=dict)

    required_json_keys: Optional[list[str]] = None  # JSON 검증용

class PolicyPreconditions(BaseModel):
    """
    특정 정책이 실행되기 위해 만족해야 하는 사전 조건 (예: RAG의 문서 검색 여부)
    """
    requires_retrieved_context: bool = False

    # 컨텍스트가 없을 때의 동작 정의 (RAG 시스템 안정성 보장용)
    # SKIP: 평가를 건너뜀 (위반 아님)
    # WARN: 평가를 건너뛰지만, 로그에 경고성으로 기록 (triggered=True)
    # FAIL: 컨텍스트 부재 자체를 시스템 오류나 우회 시도로 간주하여 즉시 차단
    no_context_behavior: Literal["SKIP", "WARN", "FAIL"] = "SKIP"


class PolicyJudgeConfig(BaseModel):
    """LLM 기반 Judge 엔진 구동을 위한 설정"""
    enabled: bool = False
    score_field: Optional[str] = None
    criteria: Optional[str] = None
    output_contract: Optional[dict[str, Any]] = None


class PolicyAction(BaseModel):
    """위반 시 실행할 액션 정의"""
    message: Optional[str] = None
    type: Optional[Literal["BLOCK", "LOG"]] = None
    fallback_response: Optional[str] = None
    default_type: Optional[Literal["BLOCK", "LOG"]] = None
    block_threshold: Optional[float] = None
    block_message: Optional[str] = None
    log_message: Optional[str] = None


class ConflictResolution(BaseModel):
    """다중 정책 위반 시 충돌 해결 전략 (추후 Interceptor에서 라우팅에 사용)"""
    block_overrides_log: bool = True
    use_policy_priority: bool = True
    fallback_message_policy: str = "highest_priority_block"


class SeverityByConfidence(BaseModel):
    high_when_confidence_gte: float
    medium_when_confidence_gte: Optional[float] = None
    low_when_confidence_gte: Optional[float] = None


class Policy(BaseModel):
    """
    단일 YAML 정책 파일 전체를 매핑하는 최상위 모델
    """
    id: str
    name: str
    version: Optional[str] = None
    enabled: bool = True

    # [아키텍처 중요] 정책의 평가 방식을 결정하는 타입
    # rule: 정규식/문자열 기반의 초고속 판단 (예: PII 마스킹, 즉시 차단 금지어)
    # judge: LLM을 이용한 의미론적 판단 (예: Groundedness)
    # hybrid: Rule로 1차 필터링 후 애매한 경우에만 Judge로 넘기는 방식 (비용 최적화)
    type: Literal["rule", "judge", "hybrid"]
    severity: Literal["low", "medium", "high"] = "medium"
    priority: int = 100

    # Judge 실행 시점 제어
    judge_required: Literal["always", "rule_triggered", "never"]

    severity_threshold: Optional[str] = None

    preconditions: Optional[PolicyPreconditions] = None
    rules: list[PolicyRule] = Field(default_factory=list)
    judge: PolicyJudgeConfig = Field(default_factory=PolicyJudgeConfig)
    action: PolicyAction
    severity_by_confidence: Optional[SeverityByConfidence] = None
    conflict_resolution: Optional[ConflictResolution] = None


class PolicyEvaluationResult(BaseModel):
    """
    Policy Engine의 최종 출력 규격.
    이 객체가 Violation Builder와 Action Engine으로 전달되어 최종 응답을 결정합니다.
    """
    policy_id: str
    policy_name: str
    triggered: bool = False # 위반 여부 (True면 위반 또는 WARN 상태)
    judge_required: bool = False # 다음 파이프라인에서 Judge 엔진을 호출해야 하는지 여부
    judge_result: dict[str, Any] | None = None
    recommended_action: Literal["BLOCK", "LOG"]
    severity: Literal["low", "medium", "high"]

    # 어떤 문장/단어 때문에 위반되었는지 하이라이팅하기 위한 증거 데이터
    evidence_spans: list[dict[str, Any]] = Field(default_factory=list)
    reason: str
    # Preconditions으로 인해 평가가 스킵된 경우 로그에서 구분하기 위한 명시적 사유 필드
    skip_reason: Optional[str] = None
