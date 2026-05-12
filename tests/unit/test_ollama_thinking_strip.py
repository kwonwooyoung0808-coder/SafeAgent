"""qwen3 등 thinking-mode 모델 응답 후처리 단위 테스트 (Phase 3-C)."""
from __future__ import annotations

from src.services.ollama_client import _NO_THINK_DIRECTIVE, _prepend_no_think, _strip_thinking


# ──────────────────────────────────────────────────────────────
# _strip_thinking
# ──────────────────────────────────────────────────────────────


def test_strip_removes_think_block():
    raw = "<think>이건 생각 과정입니다.</think>\n{\"verdict\": \"PASS\"}"
    assert _strip_thinking(raw) == '{"verdict": "PASS"}'


def test_strip_handles_multiline_think():
    raw = "<think>\n이건 여러 줄에 걸친\n추론 내용입니다.\n</think>\n실제 답변"
    assert _strip_thinking(raw) == "실제 답변"


def test_strip_leaves_text_without_think_unchanged():
    raw = '{"verdict": "PASS", "confidence": 0.9}'
    assert _strip_thinking(raw) == raw


def test_strip_handles_empty_string():
    assert _strip_thinking("") == ""


def test_strip_case_insensitive():
    raw = "<THINK>대문자 think 도 처리</THINK>본문"
    assert _strip_thinking(raw) == "본문"


def test_strip_multiple_think_blocks():
    """드물지만 모델이 여러 think 블록을 쪼개 출력하는 경우."""
    raw = "<think>1</think>중간<think>2</think>끝"
    assert _strip_thinking(raw) == "중간끝"


# ──────────────────────────────────────────────────────────────
# _prepend_no_think
# ──────────────────────────────────────────────────────────────


def test_prepend_adds_directive():
    assert _prepend_no_think("질문").startswith(_NO_THINK_DIRECTIVE)


def test_prepend_does_not_duplicate():
    """이미 디렉티브가 있으면 추가하지 않는다."""
    once = _prepend_no_think("질문")
    twice = _prepend_no_think(once)
    # 디렉티브가 한 번만 등장
    assert twice.count(_NO_THINK_DIRECTIVE) == 1


def test_prepend_handles_empty_string():
    assert _prepend_no_think("") == _NO_THINK_DIRECTIVE
