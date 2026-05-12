import pytest

from src.workflows import doc_parser_workflow


@pytest.mark.asyncio
async def test_korean_regulation_draft_skips_llm(monkeypatch) -> None:
    async def fail_if_called(*args, **kwargs):
        raise AssertionError("LLM parser should not be called for structured Korean regulations")

    monkeypatch.setattr(doc_parser_workflow, "run_two_step_llm_parse", fail_if_called)

    result = await doc_parser_workflow.llm_parser_agent_node({
        "raw_text": "제1조(목적) 회사의 비밀을 보호하여야 한다.",
        "doc_structure": {
            "korean_regulation": {
                "stats": {"article_count": 1},
                "articles": [
                    {
                        "article_no": "1",
                        "title": "목적",
                        "source_text": "제1조(목적) 회사의 비밀을 보호하여야 한다.",
                    }
                ],
            }
        },
        "warnings": [],
    })

    checks = result["extracted_rules"]["compliance_checks"]
    assert checks
    assert checks[0]["needs_review"] is True
    assert any("장시간 LLM 청킹은 건너뜁니다" in warning for warning in result["warnings"])


def test_build_criteria_uses_neutral_review_wording() -> None:
    criteria = doc_parser_workflow._build_criteria([
        {
            "id": "CC-001",
            "description": "비밀 정보를 보호하여야 한다.",
            "severity": "MEDIUM",
            "source_article": "제1조",
            "source_text": "제1조 비밀 정보를 보호하여야 한다.",
            "needs_review": True,
        }
    ])

    assert "응답 검증 기준" in criteria
    assert "위반 시 FAIL" not in criteria


@pytest.mark.asyncio
async def test_large_non_regulation_limits_llm_chunks(monkeypatch) -> None:
    calls = []

    async def fake_parse(text, client=None, structured_context=None):
        calls.append(text)
        return {"forbidden_words": [], "compliance_checks": [], "actions": {}}, []

    class Settings:
        policy_compiler_max_llm_chunks = 2

    monkeypatch.setattr(doc_parser_workflow, "run_two_step_llm_parse", fake_parse)
    monkeypatch.setattr(doc_parser_workflow, "get_settings", lambda: Settings())

    result = await doc_parser_workflow.llm_parser_agent_node({
        "raw_text": "A" * 9500,
        "doc_structure": {"headings": [], "korean_regulation": {"stats": {"article_count": 0}}},
        "warnings": [],
    })

    assert len(calls) == 2
    assert any("처리 상한 2개" in warning for warning in result["warnings"])
