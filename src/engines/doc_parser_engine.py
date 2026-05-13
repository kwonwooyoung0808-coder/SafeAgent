from __future__ import annotations

import json
import re
from pathlib import Path

from src.core.config import get_settings
from src.services.ollama_client import OllamaClient


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
        Step 1 결과를 JSON으로 변환. 추론 부담 없음.

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
    # system_prompt="" → 파일 내 역할 정의(user_message 첫 줄)가 단일 소스
    # .replace() 사용 → JSON 예시의 중괄호가 KeyError를 일으키는 문제 방지
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

    # ── Step 2: 형식 변환 (결정론적) ───────────────────────────
    try:
        json_output = await client.chat(
            system_prompt="",
            user_message=step2_tpl.replace("{reasoning_output}", reasoning),
            temperature=0.0,
        )
        extracted = _extract_json(json_output)
        if not extracted:
            warnings.append("Step 2 JSON 파싱 실패 → 빈 규칙으로 계속 진행")
    except Exception as e:
        warnings.append(f"Step 2 형식 변환 실패: {e}")
        extracted = {}

    return extracted, warnings
