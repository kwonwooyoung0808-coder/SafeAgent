from __future__ import annotations

import uuid
from datetime import date
from functools import lru_cache
from pathlib import Path

import yaml
from langgraph.graph import END, StateGraph

from src.core.config import get_settings
from src.database.connection import SessionLocal
from src.database.models import PolicyConversionLogModel, PolicyModel
from src.engines.doc_parser_engine import run_two_step_llm_parse
from src.engines.docx_chunk_processor import DocxChunkProcessor
from src.engines.docx_engine import DocxEngine
from src.engines.grounding_validator import GroundingValidator
from src.schemas.doc_parser import DocParserState
from src.schemas.policy import Policy


# ──────────────────────────────────────────────────────────────
# 액션 매핑: PRD 5.3.3 (BLOCK | LOG | FLAGGED) → Policy 스키마 (BLOCK | LOG)
# ──────────────────────────────────────────────────────────────
# 기존 PolicyAction.type Literal은 "BLOCK" | "LOG"만 허용하므로
# LLM이 "FLAGGED"를 출력해도 Pydantic 검증 통과를 위해 LOG로 매핑.
def _map_action_type(action_value: str | None) -> str:
    if action_value == "BLOCK":
        return "BLOCK"
    return "LOG"


# ──────────────────────────────────────────────────────────────
# 노드 1: DOCX 파싱 + 보안 이스케이프
# ──────────────────────────────────────────────────────────────
def docx_extractor_node(state: DocParserState) -> dict:
    """
    DocxEngine으로 문서 파싱.
    - 숨겨진 텍스트(흰색 폰트, vanish) 필터링
    - TextSanitizer로 인젝션 패턴 이스케이프
    실패 → error_message → conditional edge → END (FAILED)
    """
    try:
        engine = DocxEngine()
        result = engine.parse(state["file_path"])
        return {
            "raw_text":           result.raw_text,
            "raw_tables":         result.raw_tables,
            "doc_structure":      result.doc_structure,
            "warnings":           result.warnings,
            "injection_detected": result.injection_detected,
        }
    except Exception as e:
        return {
            "error_message":     str(e),
            "validation_passed": False,
            "warnings":          [f"docx 파싱 실패: {e}"],
        }


# ──────────────────────────────────────────────────────────────
# 노드 2: 인젝션 게이트
# ──────────────────────────────────────────────────────────────
def injection_gate_node(state: DocParserState) -> dict:
    """인젝션 탐지 시 즉시 FAILED. 정상 시 빈 dict 반환."""
    if state.get("injection_detected"):
        return {
            "validation_passed": False,
            "error_message": "SECURITY: 프롬프트 인젝션 탐지 → 처리 중단.",
            "warnings": list(state.get("warnings", [])) + [
                "SECURITY ALERT: 문서 내 인젝션 패턴 발견. "
                "보안팀에 보고 후 재업로드하세요."
            ],
        }
    return {}


# ──────────────────────────────────────────────────────────────
# 노드 3: LLM 파싱 (2단계 분리, 청킹 지원)
# ──────────────────────────────────────────────────────────────
async def llm_parser_agent_node(state: DocParserState) -> dict:
    """
    소형 문서(≤3000자): 2단계 LLM 파싱 단일 호출.
    대형 문서(>3000자): 섹션 단위 청킹 → 각 청크 2단계 파싱 → 병합.
    LLM 실패 → warnings 추가, 빈 규칙으로 계속 (PARTIAL 허용).
    """
    if state.get("error_message"):
        return {}

    raw_text = state.get("raw_text", "")
    doc_structure = state.get("doc_structure", {})
    processor = DocxChunkProcessor()
    all_warnings = list(state.get("warnings", []))

    if len(raw_text) <= DocxChunkProcessor.MAX_CHARS_PER_CHUNK:
        extracted, parse_warnings = await run_two_step_llm_parse(raw_text)
        all_warnings.extend(parse_warnings)
        return {"extracted_rules": extracted, "warnings": all_warnings}

    chunks = processor.split_by_headings(doc_structure, raw_text)
    chunk_results: list[dict] = []
    for chunk in chunks:
        result, chunk_warnings = await run_two_step_llm_parse(chunk["text"])
        chunk_results.append(result)
        all_warnings.extend(chunk_warnings)

    merged = processor.merge_results(chunk_results)
    all_warnings.append(
        f"INFO: 대형 문서 청킹 처리 완료 ({len(chunks)}개 섹션 → 병합)"
    )
    return {"extracted_rules": merged, "warnings": all_warnings}


# ──────────────────────────────────────────────────────────────
# 노드 4: YAML 직렬화 (기존 Policy 스키마 호환)
# ──────────────────────────────────────────────────────────────
def yaml_serializer_node(state: DocParserState) -> dict:
    """
    extracted_rules → 기존 Policy Pydantic 스키마(schemas/policy.py) 호환 YAML.
    policy_id = "policy-{uuid8}"
    """
    ext = state.get("extracted_rules", {})
    policy_id = f"policy-{str(uuid.uuid4())[:8]}"

    forbidden_words: list[str] = ext.get("forbidden_words", [])
    compliance_checks: list[dict] = ext.get("compliance_checks", [])
    actions: dict = ext.get("actions", {})

    on_fw = actions.get("on_forbidden_word", "BLOCK")
    rule_failure = "block_immediately" if on_fw == "BLOCK" else "judge_fallback"

    # PRD 5.3.3 → Policy 스키마 매핑 (FLAGGED는 LOG로 매핑)
    on_compliance_fail_raw = actions.get("on_compliance_fail")
    action_type = _map_action_type(on_compliance_fail_raw or on_fw)

    policy_dict = {
        "id":             policy_id,
        "name":           state["policy_name"],
        "version":        "1.0",
        "enabled":        True,
        "type":           "hybrid",
        "severity":       "high",
        "priority":       100,
        "judge_required": "rule_triggered",
        "rules": [
            {
                "condition":       "contains_categorized_forbidden_terms",
                "on_rule_failure": rule_failure,
                "parameters": {
                    "case_insensitive": True,
                    "categories": {
                        "custom_policy_terms": {
                            "enabled":     bool(forbidden_words),
                            "exact_terms": forbidden_words,
                        }
                    },
                },
            }
        ],
        "judge": {
            "enabled":  bool(compliance_checks),
            "criteria": _build_criteria(compliance_checks),
        },
        "action": {
            "type":              action_type,
            "fallback_response": "정책 위반으로 응답이 제한됩니다.",
        },
    }

    yaml_content = yaml.dump(
        policy_dict,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    )
    return {"yaml_content": yaml_content, "policy_id": policy_id}


def _build_criteria(checks: list[dict]) -> str:
    if not checks:
        return ""
    lines = ["다음 준수 항목 위반 시 FAIL:"]
    for c in checks:
        lines.append(
            f"- [{c.get('id', '')}] {c.get('description', '')} "
            f"(심각도: {c.get('severity', 'MEDIUM')})"
        )
    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────
# 노드 5: 스키마 + 그라운딩 검증
# ──────────────────────────────────────────────────────────────
def schema_validator_node(state: DocParserState) -> dict:
    """
    1단계 — Pydantic 구조 검증 (Policy 스키마 호환성)
    2단계 — GroundingValidator 내용 정확성 검증
      - forbidden_words 환각 탐지 및 제거
      - severity 오분류 탐지 및 MEDIUM 하향
      - actions 오추출 탐지 및 BLOCK 보수적 처리
    완전 실패(Pydantic 오류) → validation_passed=False → END
    부분 성공(warnings 존재) → validation_passed=True → storage_writer
    """
    warnings = list(state.get("warnings", []))
    rules = dict(state.get("extracted_rules", {}))
    raw_text = state.get("raw_text", "")

    try:
        policy_dict = yaml.safe_load(state.get("yaml_content", ""))
        Policy(**policy_dict)
        validation_passed = True
    except Exception as e:
        return {
            "validation_passed": False,
            "warnings": warnings + [f"스키마 검증 실패: {e}"],
        }

    validator = GroundingValidator()

    verified, hallucinated = validator.validate_forbidden_words(
        rules.get("forbidden_words", []), raw_text
    )
    if hallucinated:
        warnings.append(f"환각 의심 금지어 (원본 미존재, 제거됨): {hallucinated}")
        rules["forbidden_words"] = verified

    validated_checks, sev_warnings = validator.validate_severity_grounding(
        rules.get("compliance_checks", []), raw_text
    )
    warnings.extend(sev_warnings)
    rules["compliance_checks"] = validated_checks

    validated_actions, act_warnings = validator.validate_actions(
        rules.get("actions", {}), raw_text
    )
    warnings.extend(act_warnings)
    rules["actions"] = validated_actions

    if not rules.get("forbidden_words"):
        warnings.append(
            "WARNING: forbidden_words가 비어 있음 → LLM 추출 누락 가능. 수동 검토 필요."
        )

    return {
        "extracted_rules":   rules,
        "validation_passed": validation_passed,
        "warnings":          warnings,
    }


# ──────────────────────────────────────────────────────────────
# 노드 6: 저장 (YAML 파일 + DB INSERT)
# ──────────────────────────────────────────────────────────────
def storage_writer_node(state: DocParserState) -> dict:
    """
    1) YAML 파일 저장: {policy_dir}/{policy_id}.yaml (UTF-8)
    2) policies INSERT (is_active=FALSE → Feature 1/2 즉시 영향 없음)
    3) policy_conversion_logs INSERT
    DB 실패 시 YAML은 보존, warnings에 기록.
    """
    settings = get_settings()
    policy_id = state["policy_id"]
    warnings = list(state.get("warnings", []))

    policy_dir = Path(settings.policy_dir)
    policy_dir.mkdir(parents=True, exist_ok=True)
    yaml_path = str(policy_dir / f"{policy_id}.yaml")
    Path(yaml_path).write_text(state["yaml_content"], encoding="utf-8")

    try:
        eff_date = date.fromisoformat(state.get("effective_date", ""))
    except (ValueError, TypeError):
        eff_date = None

    status = "PARTIAL" if warnings else "SUCCESS"

    # parsed_rules_count: forbidden_words + compliance_checks 개수
    # (라우터의 동일 필드 계산식과 정합성 보장)
    ext_rules = state.get("extracted_rules", {})
    parsed_count = (
        len(ext_rules.get("forbidden_words", []))
        + len(ext_rules.get("compliance_checks", []))
    )

    session = SessionLocal()
    try:
        session.add(PolicyModel(
            id=policy_id,
            name=state["policy_name"],
            version="1.0",
            yaml_path=yaml_path,
            effective_date=eff_date,
            is_active=False,
        ))
        session.add(PolicyConversionLogModel(
            id=str(uuid.uuid4()),
            policy_id=policy_id,
            original_filename=Path(state["file_path"]).name,
            parsed_rules_count=parsed_count,
            conversion_status=status,
            warnings=warnings,
        ))
        session.commit()
    except Exception as e:
        session.rollback()
        warnings.append(f"DB 저장 실패 (YAML은 보존됨): {e}")
    finally:
        session.close()

    return {"yaml_path": yaml_path, "warnings": warnings}


# ──────────────────────────────────────────────────────────────
# 그래프 조립
# ──────────────────────────────────────────────────────────────
@lru_cache
def build_doc_parser_graph():
    graph = StateGraph(DocParserState)

    graph.add_node("docx_extractor",   docx_extractor_node)
    graph.add_node("injection_gate",   injection_gate_node)
    graph.add_node("llm_parser_agent", llm_parser_agent_node)
    graph.add_node("yaml_serializer",  yaml_serializer_node)
    graph.add_node("schema_validator", schema_validator_node)
    graph.add_node("storage_writer",   storage_writer_node)

    graph.set_entry_point("docx_extractor")

    graph.add_conditional_edges(
        "docx_extractor",
        lambda s: END if s.get("error_message") else "injection_gate",
        {END: END, "injection_gate": "injection_gate"},
    )
    graph.add_conditional_edges(
        "injection_gate",
        lambda s: END if s.get("injection_detected") else "llm_parser_agent",
        {END: END, "llm_parser_agent": "llm_parser_agent"},
    )
    graph.add_edge("llm_parser_agent", "yaml_serializer")
    graph.add_edge("yaml_serializer",  "schema_validator")
    graph.add_conditional_edges(
        "schema_validator",
        lambda s: "storage_writer" if s.get("validation_passed") else END,
        {"storage_writer": "storage_writer", END: END},
    )
    graph.add_edge("storage_writer", END)

    return graph.compile()
