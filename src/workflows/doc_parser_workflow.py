from __future__ import annotations

import os
import tempfile
import uuid
from datetime import date
from functools import lru_cache
from pathlib import Path

import yaml
from langgraph.graph import END, StateGraph
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from src.core.config import get_settings
from src.database.connection import SessionLocal
from src.database.models import PolicyConversionLogModel, PolicyModel, PolicyVersionModel
from src.engines.doc_parser_engine import run_two_step_llm_parse
from src.engines.docx_chunk_processor import DocxChunkProcessor
from src.engines.docx_engine import DocxEngine
from src.engines.grounding_validator import GroundingValidator
from src.engines.korean_regulation_parser import regulation_to_llm_context
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


_REGULATION_POLICY_KEYWORDS = (
    "하여야",
    "해야",
    "한다",
    "금지",
    "불가",
    "제한",
    "승인",
    "보고",
    "관리",
    "보호",
    "보안",
    "비밀",
    "책임",
    "점검",
    "기록",
)


def _safe_unlink_policy_artifact(path: Path, policy_dir: Path, policy_id: str) -> None:
    """Delete only this request's policy artifact inside policy_dir."""
    try:
        resolved_dir = policy_dir.resolve()
        resolved_path = path.resolve()
    except OSError:
        return
    expected_name = f"{policy_id}.yaml"
    tmp_prefix = f".{policy_id}."
    is_expected_final = resolved_path.name == expected_name
    is_expected_tmp = resolved_path.name.startswith(tmp_prefix) and resolved_path.suffix == ".tmp"
    if resolved_path.parent == resolved_dir and (is_expected_final or is_expected_tmp):
        try:
            resolved_path.unlink(missing_ok=True)
        except OSError:
            pass


def _needs_draft_fallback(extracted: dict) -> bool:
    return not (
        extracted.get("forbidden_words")
        or extracted.get("compliance_checks")
        or extracted.get("actions")
    )


def _build_draft_rules_from_regulation(regulation: dict) -> dict:
    """LLM 추출이 비었을 때 한국식 조문 구조에서 검토용 정책 draft를 만든다."""
    checks: list[dict] = []
    for article in regulation.get("articles", []):
        source_text = article.get("source_text", "").strip()
        if not source_text:
            continue
        if not any(keyword in source_text for keyword in _REGULATION_POLICY_KEYWORDS):
            continue
        article_label = f"제{article.get('article_no')}조"
        title = article.get("title") or ""
        checks.append({
            "id": f"CC-{len(checks) + 1:03d}",
            "description": f"{article_label}({title}) 준수 여부 확인: {source_text[:220]}",
            "severity": "MEDIUM",
            "source_article": article_label,
            "source_text": source_text[:1200],
            "needs_review": True,
        })
        if len(checks) >= 80:
            break

    return {
        "forbidden_words": [],
        "compliance_checks": checks,
        "actions": {
            "on_forbidden_word": "LOG",
            "on_compliance_fail": "LOG",
        },
        "warnings": [
            "LLM 추출 결과가 비어 있거나 부족하여 한국식 조문 파서 기반 검토용 draft를 생성했습니다.",
            "severity/action은 문서에 명시되지 않은 경우 MEDIUM/LOG로 보수 적용했습니다.",
        ],
    }


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
    regulation = doc_structure.get("korean_regulation", {})
    structured_context = regulation_to_llm_context(regulation)
    processor = DocxChunkProcessor()
    all_warnings = list(state.get("warnings", []))
    article_count = regulation.get("stats", {}).get("article_count", 0)

    if article_count:
        extracted = _build_draft_rules_from_regulation(regulation)
        all_warnings.extend(extracted.get("warnings", []))
        all_warnings.append(
            f"INFO: 한국식 조문 {article_count}개를 구조화 draft로 변환했습니다. "
            "장시간 LLM 청킹은 건너뜁니다."
        )
        return {"extracted_rules": extracted, "warnings": all_warnings}

    if len(raw_text) <= DocxChunkProcessor.MAX_CHARS_PER_CHUNK:
        extracted, parse_warnings = await run_two_step_llm_parse(
            raw_text,
            structured_context=structured_context,
        )
        all_warnings.extend(parse_warnings)
        if _needs_draft_fallback(extracted):
            extracted = _build_draft_rules_from_regulation(regulation)
            all_warnings.extend(extracted.get("warnings", []))
        return {"extracted_rules": extracted, "warnings": all_warnings}

    chunks = processor.split_by_headings(doc_structure, raw_text)
    settings = get_settings()
    max_chunks = max(1, settings.policy_compiler_max_llm_chunks)
    original_chunk_count = len(chunks)
    if original_chunk_count > max_chunks:
        chunks = chunks[:max_chunks]
        all_warnings.append(
            f"WARNING: 대형 문서 LLM 청크가 {original_chunk_count}개로 많아 "
            f"처리 상한 {max_chunks}개까지만 자동 변환했습니다. 나머지는 수동 검토가 필요합니다."
        )
    chunk_results: list[dict] = []
    for chunk in chunks:
        result, chunk_warnings = await run_two_step_llm_parse(
            chunk["text"],
            structured_context=chunk["text"],
        )
        chunk_results.append(result)
        all_warnings.extend(chunk_warnings)

    merged = processor.merge_results(chunk_results)
    if _needs_draft_fallback(merged):
        merged = _build_draft_rules_from_regulation(regulation)
        all_warnings.extend(merged.get("warnings", []))
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
    policy_id comes from the upload form and is validated by the router.
    """
    ext = state.get("extracted_rules", {})
    policy_id = state.get("policy_id")
    if not policy_id:
        raise ValueError("policy_id is required for policy compiler output")

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
        "enabled":        False,
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

    yaml_content = yaml.safe_dump(
        policy_dict,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    )
    return {"yaml_content": yaml_content, "policy_id": policy_id}


def _build_criteria(checks: list[dict]) -> str:
    if not checks:
        return ""
    lines = [
        "다음 항목은 회사 규정 문서에서 추출한 응답 검증 기준입니다:",
        "이 YAML은 회사 규정 문서에서 생성된 검토용 draft입니다.",
        "source_article/source_text를 기준으로 담당자가 최종 검토해야 합니다.",
    ]
    for c in checks:
        lines.append(
            f"- [{c.get('id', '')}] {c.get('description', '')} "
            f"(심각도: {c.get('severity', 'MEDIUM')})"
        )
        if c.get("source_article"):
            lines.append(f"  근거 조항: {c.get('source_article')}")
        if c.get("source_text"):
            lines.append(f"  근거 원문: {c.get('source_text')[:500]}")
        if c.get("needs_review"):
            lines.append("  검토 필요: true")
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

    is_review_draft = any(
        check.get("needs_review") for check in rules.get("compliance_checks", [])
    )
    if is_review_draft:
        warnings.append("INFO: 검토용 draft 정책이므로 action 자동 강화 검증을 건너뜁니다.")
    else:
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
    """Persist YAML and DB rows, cleaning up only artifacts from this request."""
    settings = get_settings()
    policy_id = state["policy_id"]
    warnings = list(state.get("warnings", []))

    policy_dir = Path(settings.policy_dir)
    policy_dir.mkdir(parents=True, exist_ok=True)
    final_path = policy_dir / f"{policy_id}.yaml"
    yaml_path: str | None = str(final_path)
    tmp_path: Path | None = None
    final_created_by_request = False

    if final_path.exists():
        warnings.append(f"YAML 저장 실패: 이미 같은 policy_id 파일이 존재합니다: {final_path}")
        return {"yaml_path": None, "warnings": warnings}

    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            suffix=".tmp",
            prefix=f".{policy_id}.",
            dir=policy_dir,
            delete=False,
        ) as tmp:
            tmp.write(state["yaml_content"])
            tmp_path = Path(tmp.name)
    except OSError as e:
        warnings.append(f"YAML 임시 파일 저장 실패: {e}")
        if tmp_path is not None:
            _safe_unlink_policy_artifact(tmp_path, policy_dir, policy_id)
        return {"yaml_path": None, "warnings": warnings}

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
        # PolicyConversionLogModel.policy_id has an FK to policies.id. Flush the
        # parent first because these models do not declare ORM relationships that
        # would let SQLAlchemy infer insert ordering automatically.
        session.flush()
        session.add(PolicyConversionLogModel(
            id=str(uuid.uuid4()),
            policy_id=policy_id,
            requested_policy_id=policy_id,
            original_filename=Path(state["file_path"]).name,
            parsed_rules_count=parsed_count,
            conversion_status=status,
            warnings=warnings,
        ))
        session.add(PolicyVersionModel(
            id=str(uuid.uuid4()),
            policy_id=policy_id,
            version="1.0",
            yaml_path=yaml_path,
            yaml_snapshot=state["yaml_content"],
            is_current=False,
            activated_at=None,
        ))
        session.flush()
        if tmp_path is None:
            raise OSError("YAML temporary file is missing")
        os.replace(tmp_path, final_path)
        tmp_path = None
        final_created_by_request = True
        session.commit()
    except IntegrityError as e:
        session.rollback()
        warnings.append(f"DB 무결성 저장 실패로 YAML 산출물을 정리했습니다: {e}")
        if tmp_path is not None:
            _safe_unlink_policy_artifact(tmp_path, policy_dir, policy_id)
        if final_created_by_request:
            _safe_unlink_policy_artifact(final_path, policy_dir, policy_id)
        yaml_path = None
    except SQLAlchemyError as e:
        session.rollback()
        warnings.append(f"DB 저장 실패로 YAML 산출물을 정리했습니다: {e}")
        if tmp_path is not None:
            _safe_unlink_policy_artifact(tmp_path, policy_dir, policy_id)
        if final_created_by_request:
            _safe_unlink_policy_artifact(final_path, policy_dir, policy_id)
        yaml_path = None
    except OSError as e:
        session.rollback()
        warnings.append(f"YAML 최종 파일 저장 실패로 DB 저장을 취소했습니다: {e}")
        if tmp_path is not None:
            _safe_unlink_policy_artifact(tmp_path, policy_dir, policy_id)
        if final_created_by_request:
            _safe_unlink_policy_artifact(final_path, policy_dir, policy_id)
        yaml_path = None
    except Exception as e:
        session.rollback()
        warnings.append(f"정책 저장 중 예상하지 못한 오류로 YAML 산출물을 정리했습니다: {e}")
        if tmp_path is not None:
            _safe_unlink_policy_artifact(tmp_path, policy_dir, policy_id)
        if final_created_by_request:
            _safe_unlink_policy_artifact(final_path, policy_dir, policy_id)
        yaml_path = None
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
