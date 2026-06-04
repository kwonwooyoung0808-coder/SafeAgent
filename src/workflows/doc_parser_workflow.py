from __future__ import annotations

import asyncio
import json
import os
import re
import tempfile
import time
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
from src.engines.korean_regulation_parser import (
    extract_forbidden_terms_from_articles,
    regulation_to_llm_context,
)
from src.schemas.doc_parser import DocParserState
from src.schemas.policy import Policy
from src.services.ollama_client import OllamaClient


# ──────────────────────────────────────────────────────────────
# 액션 매핑: PRD 5.3.3 (BLOCK | LOG | FLAGGED) → Policy 스키마 (BLOCK | LOG)
# ──────────────────────────────────────────────────────────────
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

    # Phase 1-A: 규칙 기반 금지어 후보 추출 (LLM 없이)
    forbidden_candidates = extract_forbidden_terms_from_articles(
        regulation.get("articles", [])
    )

    return {
        "forbidden_words": forbidden_candidates,
        "compliance_checks": checks,
        "actions": {
            "on_forbidden_word": "LOG",
            "on_compliance_fail": "LOG",
        },
        "warnings": [
            "LLM 추출 결과가 비어 있거나 부족하여 한국식 조문 파서 기반 검토용 draft를 생성했습니다.",
            "severity/action은 문서에 명시되지 않은 경우 MEDIUM/LOG로 보수 적용했습니다.",
            f"규칙 기반 금지어 후보 {len(forbidden_candidates)}개 추출됨 — 수동 검토 필요.",
        ],
    }


# ── Phase 1-B: 금지어 전용 경량 LLM 호출 ─────────────────────────────────
async def _extract_forbidden_words_llm(
    document_text: str,
    client: OllamaClient | None = None,
) -> tuple[list[str], list[str]]:
    """
    금지어 전용 단일 LLM 프롬프트 호출.
    한국식 조문 문서에서 2단계 full parse 없이 금지어만 빠르게 추출한다.
    """
    if client is None:
        client = OllamaClient()

    settings = get_settings()
    prompt_path = Path(settings.prompt_dir) / "doc_parser_forbidden_words.txt"
    warnings: list[str] = []

    if not prompt_path.exists():
        warnings.append("금지어 전용 프롬프트 파일 없음 — 규칙 기반 결과만 사용합니다.")
        return [], warnings

    prompt_tpl = prompt_path.read_text(encoding="utf-8")
    # 앞 3000자만 사용 (경량 호출)
    snippet = document_text[:3000]

    try:
        raw = await client.chat(
            system_prompt="",
            user_message=prompt_tpl.replace("{document_text}", snippet),
            temperature=0.0,
        )
        # JSON 배열 파싱
        m = re.search(r"\[.*?\]", raw, re.DOTALL)
        if m:
            words = json.loads(m.group(0))
            if isinstance(words, list):
                return [str(w).strip() for w in words if str(w).strip()], warnings
        warnings.append("금지어 전용 LLM 호출: JSON 배열 파싱 실패 — 규칙 기반 결과만 사용합니다.")
    except Exception as e:
        warnings.append(f"금지어 전용 LLM 호출 실패: {e} — 규칙 기반 결과만 사용합니다.")

    return [], warnings


# ──────────────────────────────────────────────────────────────
# 노드 1: DOCX 파싱 + 보안 이스케이프
# ──────────────────────────────────────────────────────────────
def docx_extractor_node(state: DocParserState) -> dict:
    t0 = time.perf_counter()
    try:
        engine = DocxEngine()
        result = engine.parse(state["file_path"])
        elapsed = time.perf_counter() - t0
        timings = dict(state.get("node_timings") or {})
        timings["docx_extractor"] = round(elapsed, 3)
        return {
            "raw_text":           result.raw_text,
            "raw_tables":         result.raw_tables,
            "doc_structure":      result.doc_structure,
            "warnings":           result.warnings,
            "injection_detected": result.injection_detected,
            "node_timings":       timings,
        }
    except Exception as e:
        elapsed = time.perf_counter() - t0
        timings = dict(state.get("node_timings") or {})
        timings["docx_extractor"] = round(elapsed, 3)
        return {
            "error_message":     str(e),
            "validation_passed": False,
            "warnings":          [f"docx 파싱 실패: {e}"],
            "node_timings":      timings,
        }


# ──────────────────────────────────────────────────────────────
# 노드 2: 인젝션 게이트
# ──────────────────────────────────────────────────────────────
def injection_gate_node(state: DocParserState) -> dict:
    t0 = time.perf_counter()
    timings = dict(state.get("node_timings") or {})
    if state.get("injection_detected"):
        timings["injection_gate"] = round(time.perf_counter() - t0, 3)
        return {
            "validation_passed": False,
            "error_message": "SECURITY: 프롬프트 인젝션 탐지 → 처리 중단.",
            "warnings": list(state.get("warnings", [])) + [
                "SECURITY ALERT: 문서 내 인젝션 패턴 발견. "
                "보안팀에 보고 후 재업로드하세요."
            ],
            "node_timings": timings,
        }
    timings["injection_gate"] = round(time.perf_counter() - t0, 3)
    return {"node_timings": timings}


# 금지어 전용 LLM 호출 임계값 — 규칙 기반 결과가 이 수치 미만일 때만 LLM 보강
_FORBIDDEN_LLM_THRESHOLD = 3


# ──────────────────────────────────────────────────────────────
# 노드 3: LLM 파싱 (Phase 1-B 금지어 전용 호출 + Phase 3-A 청크 병렬화)
# ──────────────────────────────────────────────────────────────
async def llm_parser_agent_node(state: DocParserState) -> dict:
    t0 = time.perf_counter()
    timings = dict(state.get("node_timings") or {})
    llm_call_count = int(state.get("llm_call_count", 0))
    chunk_count = int(state.get("chunk_count", 0))

    if state.get("error_message"):
        timings["llm_parser_agent"] = round(time.perf_counter() - t0, 3)
        return {
            "node_timings":   timings,
            "llm_call_count": llm_call_count,
            "chunk_count":    chunk_count,
        }

    raw_text = state.get("raw_text", "")
    doc_structure = state.get("doc_structure", {})
    regulation = doc_structure.get("korean_regulation", {})
    structured_context = regulation_to_llm_context(regulation)
    processor = DocxChunkProcessor()
    all_warnings = list(state.get("warnings", []))
    article_count = regulation.get("stats", {}).get("article_count", 0)

    if article_count:
        # 구조화 draft 먼저 생성 (규칙 기반 금지어 포함)
        extracted = _build_draft_rules_from_regulation(regulation)
        all_warnings.extend(extracted.get("warnings", []))
        rule_based = extracted.get("forbidden_words", [])

        # Fix 7: 규칙 기반 결과가 임계값 미만일 때만 LLM 보강 호출
        if len(rule_based) < _FORBIDDEN_LLM_THRESHOLD:
            llm_fw, llm_fw_warnings = await _extract_forbidden_words_llm(raw_text)
            llm_call_count += 1
            all_warnings.extend(llm_fw_warnings)
            if llm_fw:
                merged_fw = list(dict.fromkeys(llm_fw + rule_based))
                extracted["forbidden_words"] = merged_fw
                all_warnings.append(
                    f"INFO: 규칙 기반 {len(rule_based)}개 < 임계값 → 금지어 LLM 호출. "
                    f"LLM {len(llm_fw)}개 + 규칙 {len(rule_based)}개 → 병합 {len(merged_fw)}개."
                )
            else:
                all_warnings.append(
                    f"INFO: 규칙 기반 {len(rule_based)}개 + LLM 보강 0개."
                )
        else:
            all_warnings.append(
                f"INFO: 규칙 기반 금지어 {len(rule_based)}개 ≥ 임계값 → LLM 호출 생략 "
                f"(대기 시간 절감)."
            )

        timings["llm_parser_agent"] = round(time.perf_counter() - t0, 3)
        return {
            "extracted_rules": extracted,
            "warnings":        all_warnings,
            "node_timings":    timings,
            "llm_call_count":  llm_call_count,
            "chunk_count":     chunk_count,
        }

    if len(raw_text) <= DocxChunkProcessor.MAX_CHARS_PER_CHUNK:
        extracted, parse_warnings = await run_two_step_llm_parse(
            raw_text,
            structured_context=structured_context,
        )
        llm_call_count += 2  # Step 1 + Step 2
        all_warnings.extend(parse_warnings)
        if _needs_draft_fallback(extracted):
            extracted = _build_draft_rules_from_regulation(regulation)
            all_warnings.extend(extracted.get("warnings", []))
        timings["llm_parser_agent"] = round(time.perf_counter() - t0, 3)
        return {
            "extracted_rules": extracted,
            "warnings":        all_warnings,
            "node_timings":    timings,
            "llm_call_count":  llm_call_count,
            "chunk_count":     chunk_count,
        }

    # Phase 3-A: 대형 문서 — 청크 병렬 처리
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

    chunk_count = len(chunks)

    # asyncio.gather로 청크 병렬 파싱
    parse_tasks = [
        run_two_step_llm_parse(chunk["text"], structured_context=chunk["text"])
        for chunk in chunks
    ]
    chunk_outputs = await asyncio.gather(*parse_tasks, return_exceptions=True)
    # 각 청크는 Step 1 + Step 2 = 2회 호출 (실패 청크는 0~2회지만 보수적으로 카운트)
    llm_call_count += chunk_count * 2

    chunk_results: list[dict] = []
    for i, output in enumerate(chunk_outputs):
        if isinstance(output, Exception):
            all_warnings.append(f"청크 {i + 1} 파싱 오류: {output}")
            chunk_results.append({})
        else:
            result, chunk_warnings = output
            chunk_results.append(result)
            all_warnings.extend(chunk_warnings)

    merged = processor.merge_results(chunk_results)
    if _needs_draft_fallback(merged):
        merged = _build_draft_rules_from_regulation(regulation)
        all_warnings.extend(merged.get("warnings", []))
    all_warnings.append(
        f"INFO: 대형 문서 청킹 병렬 처리 완료 ({chunk_count}개 섹션 → 병합)"
    )

    timings["llm_parser_agent"] = round(time.perf_counter() - t0, 3)
    return {
        "extracted_rules": merged,
        "warnings":        all_warnings,
        "node_timings":    timings,
        "llm_call_count":  llm_call_count,
        "chunk_count":     chunk_count,
    }


# ──────────────────────────────────────────────────────────────
# 노드 4: YAML 직렬화 (기존 Policy 스키마 호환)
# ──────────────────────────────────────────────────────────────
def yaml_serializer_node(state: DocParserState) -> dict:
    t0 = time.perf_counter()
    timings = dict(state.get("node_timings") or {})

    ext = state.get("extracted_rules", {})
    policy_id = state.get("policy_id")
    if not policy_id:
        raise ValueError("policy_id is required for policy compiler output")

    forbidden_words: list[str] = ext.get("forbidden_words", [])
    compliance_checks: list[dict] = ext.get("compliance_checks", [])
    actions: dict = ext.get("actions", {})

    on_fw = actions.get("on_forbidden_word", "BLOCK")
    rule_failure = "block_immediately" if on_fw == "BLOCK" else "judge_fallback"

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
    timings["yaml_serializer"] = round(time.perf_counter() - t0, 3)
    return {
        "yaml_content": yaml_content,
        "policy_id":    policy_id,
        "node_timings": timings,
    }


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
    t0 = time.perf_counter()
    timings = dict(state.get("node_timings") or {})
    hallucination_count = int(state.get("hallucination_removals_count", 0))

    warnings = list(state.get("warnings", []))
    rules = dict(state.get("extracted_rules", {}))
    raw_text = state.get("raw_text", "")

    try:
        policy_dict = yaml.safe_load(state.get("yaml_content", ""))
        Policy(**policy_dict)
        validation_passed = True
    except Exception as e:
        timings["schema_validator"] = round(time.perf_counter() - t0, 3)
        return {
            "validation_passed":            False,
            "warnings":                     warnings + [f"스키마 검증 실패: {e}"],
            "node_timings":                 timings,
            "hallucination_removals_count": hallucination_count,
        }

    validator = GroundingValidator()

    verified, hallucinated = validator.validate_forbidden_words(
        rules.get("forbidden_words", []), raw_text
    )
    if hallucinated:
        warnings.append(f"환각 의심 금지어 (원본 미존재, 제거됨): {hallucinated}")
        rules["forbidden_words"] = verified
        # Fix 1: 환각 제거 수 카운트
        hallucination_count += len(hallucinated)

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

    timings["schema_validator"] = round(time.perf_counter() - t0, 3)
    return {
        "extracted_rules":              rules,
        "validation_passed":            validation_passed,
        "warnings":                     warnings,
        "node_timings":                 timings,
        "hallucination_removals_count": hallucination_count,
    }


# ──────────────────────────────────────────────────────────────
# 노드 6: 저장 (YAML 파일 + DB INSERT) — Phase 4-A 타이밍 로그 포함
# ──────────────────────────────────────────────────────────────
def storage_writer_node(state: DocParserState) -> dict:
    t0 = time.perf_counter()
    settings = get_settings()
    policy_id = state["policy_id"]
    warnings = list(state.get("warnings", []))
    timings = dict(state.get("node_timings") or {})
    llm_call_count = int(state.get("llm_call_count", 0))
    chunk_count = int(state.get("chunk_count", 0))
    hallucination_count = int(state.get("hallucination_removals_count", 0))

    def _abort(extra_warning: str) -> dict:
        """Fix 6: 조기 반환 시 timings + 메트릭을 일관되게 전달."""
        warnings.append(extra_warning)
        timings["storage_writer"] = round(time.perf_counter() - t0, 3)
        return {
            "yaml_path":                    None,
            "warnings":                     warnings,
            "node_timings":                 timings,
            "llm_call_count":               llm_call_count,
            "chunk_count":                  chunk_count,
            "hallucination_removals_count": hallucination_count,
        }

    policy_dir = Path(settings.policy_dir)
    policy_dir.mkdir(parents=True, exist_ok=True)
    final_path = policy_dir / f"{policy_id}.yaml"
    yaml_path: str | None = str(final_path)
    tmp_path: Path | None = None
    final_created_by_request = False

    if final_path.exists():
        return _abort(
            f"YAML 저장 실패: 이미 같은 policy_id 파일이 존재합니다: {final_path}"
        )

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
        if tmp_path is not None:
            _safe_unlink_policy_artifact(tmp_path, policy_dir, policy_id)
        return _abort(f"YAML 임시 파일 저장 실패: {e}")

    try:
        eff_date = date.fromisoformat(state.get("effective_date", ""))
    except (ValueError, TypeError):
        eff_date = None

    status = "PARTIAL" if warnings else "SUCCESS"

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
        session.flush()
        # Fix 6: DB 트랜잭션 후에 storage_writer 타이밍 측정 (실제 작업 포함)
        timings["storage_writer"] = round(time.perf_counter() - t0, 3)
        total_latency_ms = round(sum(timings.values()) * 1000)
        warnings.append(
            f"TIMING: 전체 {total_latency_ms}ms — "
            + ", ".join(f"{k}={v:.3f}s" for k, v in timings.items())
        )
        session.add(PolicyConversionLogModel(
            id=str(uuid.uuid4()),
            policy_id=policy_id,
            requested_policy_id=policy_id,
            original_filename=Path(state["file_path"]).name,
            parsed_rules_count=parsed_count,
            conversion_status=status,
            warnings=warnings,
            total_latency_ms=total_latency_ms,
            llm_call_count=llm_call_count,
            chunk_count=chunk_count,
            hallucination_removals_count=hallucination_count,
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

    return {
        "yaml_path":                    yaml_path,
        "warnings":                     warnings,
        "node_timings":                 timings,
        "llm_call_count":               llm_call_count,
        "chunk_count":                  chunk_count,
        "hallucination_removals_count": hallucination_count,
    }


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
