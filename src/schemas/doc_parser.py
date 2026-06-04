from __future__ import annotations

from typing import Any, Literal, TypedDict

from pydantic import BaseModel, Field


class PolicyConvertResponse(BaseModel):
    policy_id: str | None = None
    yaml_path: str | None = None
    status: Literal["SUCCESS", "PARTIAL", "FAILED"]
    parsed_rules_count: int = 0
    warnings: list[str] = Field(default_factory=list)


class DocParserState(TypedDict, total=False):
    """LangGraph 상태 — Feature 3 .docx → YAML 변환 노드 간 전달."""

    file_path: str
    policy_name: str
    effective_date: str

    raw_text: str
    raw_tables: list[Any]
    doc_structure: dict[str, Any]
    injection_detected: bool

    extracted_rules: dict[str, Any]
    yaml_content: str
    yaml_path: str
    policy_id: str

    validation_passed: bool
    warnings: list[str]
    error_message: str

    # Phase 4-A: 노드별 실행 시간 (초 단위)
    node_timings: dict[str, float]

    # Phase 4-B: 메트릭 카운터
    llm_call_count: int
    chunk_count: int
    hallucination_removals_count: int
