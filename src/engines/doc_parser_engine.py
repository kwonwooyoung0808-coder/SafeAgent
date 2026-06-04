from __future__ import annotations

import json
import re
from pathlib import Path

from src.core.config import get_settings
from src.services.ollama_client import OllamaClient

# Phase 2-A: Step 2 JSON Schema — Ollama structured output 강제
_STEP2_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "forbidden_words": {
            "type": "array",
            "items": {"type": "string"},
        },
        "compliance_checks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id":             {"type": "string"},
                    "description":    {"type": "string"},
                    "severity":       {"type": "string", "enum": ["HIGH", "MEDIUM", "LOW"]},
                    "source_article": {"type": "string"},
                    "source_text":    {"type": "string"},
                    "needs_review":   {"type": "boolean"},
                },
                "required": ["id", "description", "severity"],
            },
        },
        "actions": {
            "type": "object",
            "properties": {
                "on_forbidden_word":  {"type": "string", "enum": ["BLOCK", "LOG", "FLAGGED"]},
                "on_compliance_fail": {"type": "string", "enum": ["BLOCK", "LOG", "FLAGGED"]},
            },
        },
        "warnings": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["forbidden_words", "compliance_checks", "actions", "warnings"],
}

_MAX_RETRIES = 2


def _extract_json(raw: str) -> dict:
    """LLM 응답에서 JSON 블록 추출. 실패 시 빈 dict 반환."""
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return {}


async def run_two_step_llm_parse(
    sanitized_text: str,
    client: OllamaClient | None = None,
    structured_context: str | None = None,
) -> tuple[dict, list[str]]:
    """
    NL-to-Format 2단계 분리 파싱.

    Step 1 — 의미 추론 (temperature=0.1, 포맷 제약 없음)
        LLM이 문서를 자연어로 분석. Chain-of-Thought 활성화.

    Step 2 — 형식 변환만 (temperature=0.0, 결정론적)
        Step 1 결과를 JSON으로 변환. Ollama JSON Schema 강제화.
        Phase 2-B: 파싱 실패 시 최대 _MAX_RETRIES회 재시도.

    Returns:
        extracted_rules: 추출된 정책 규칙 dict
        warnings: 실패/경고 목록
    """
    if client is None:
        client = OllamaClient()

    settings = get_settings()
    prompt_dir = Path(settings.prompt_dir)
    warnings: list[str] = []

    step1_path = prompt_dir / "doc_parser_step1_reasoning.txt"
    step2_path = prompt_dir / "doc_parser_step2_format.txt"

    if not step1_path.exists() or not step2_path.exists():
        warnings.append(
            "프롬프트 파일 없음: doc_parser_step1_reasoning.txt / "
            "doc_parser_step2_format.txt — 사용자가 작성해야 합니다."
        )
        return {}, warnings

    step1_tpl = step1_path.read_text(encoding="utf-8")
    step2_tpl = step2_path.read_text(encoding="utf-8")

    # ── Step 1: 의미 추론 ──────────────────────────────────────
    try:
        reasoning = await client.chat(
            system_prompt="",
            user_message=step1_tpl
            .replace("{sanitized_raw_text}", sanitized_text)
            .replace("{structured_context}", structured_context or sanitized_text),
            temperature=0.1,
        )
    except Exception as e:
        warnings.append(f"Step 1 추론 실패: {e}")
        return {}, warnings

    # ── Step 2: 형식 변환 — JSON Schema 강제화 + 재시도 ────────
    # Fix 2: 재시도 시 temperature 점진 증가 + 재시도 힌트 prefix 추가로
    # 동일 입력 → 동일 출력 문제 해결.
    extracted: dict = {}
    base_step2 = step2_tpl.replace("{reasoning_output}", reasoning)
    retry_temperatures = [0.0, 0.15, 0.3]  # 시도별 temperature
    retry_hints = [
        "",
        "\n\n[재시도] 이전 응답이 유효한 JSON 형식이 아니었습니다. 위 JSON 구조를 정확히 따라주세요.",
        "\n\n[최종 재시도] 반드시 JSON 객체만 출력하세요. 다른 텍스트 일체 금지.",
    ]
    for attempt in range(_MAX_RETRIES + 1):
        try:
            user_msg = base_step2 + retry_hints[min(attempt, len(retry_hints) - 1)]
            json_output = await client.chat(
                system_prompt="",
                user_message=user_msg,
                temperature=retry_temperatures[min(attempt, len(retry_temperatures) - 1)],
                json_schema=_STEP2_JSON_SCHEMA,  # Phase 2-A
            )
            # JSON Schema 모드에서는 응답 자체가 JSON이지만 방어적으로 추출 시도
            parsed = _extract_json(json_output)
            if not parsed:
                # Schema 모드 응답이 직접 JSON 문자열인 경우
                try:
                    parsed = json.loads(json_output)
                except json.JSONDecodeError:
                    parsed = {}

            if parsed:
                extracted = parsed
                if attempt > 0:
                    warnings.append(f"Step 2 시도 {attempt + 1}회차에서 성공.")
                break
            else:
                warnings.append(
                    f"Step 2 JSON 파싱 실패 (시도 {attempt + 1}/{_MAX_RETRIES + 1})"
                )
        except Exception as e:
            warnings.append(
                f"Step 2 형식 변환 실패 (시도 {attempt + 1}/{_MAX_RETRIES + 1}): {e}"
            )

    if not extracted:
        warnings.append("Step 2 최종 실패 → 빈 규칙으로 계속 진행")

    return extracted, warnings
