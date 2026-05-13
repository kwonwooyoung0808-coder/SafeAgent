import pytest
from sqlalchemy.exc import SQLAlchemyError

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


def _storage_state(policy_id: str) -> dict:
    return {
        "policy_id": policy_id,
        "policy_name": "Storage Policy",
        "effective_date": "2026-05-12",
        "file_path": "source.docx",
        "yaml_content": "id: TEST\nname: Test\n",
        "extracted_rules": {
            "forbidden_words": [],
            "compliance_checks": [{"id": "CC-001"}],
        },
        "warnings": [],
    }


class _Settings:
    def __init__(self, policy_dir):
        self.policy_dir = str(policy_dir)


class _FakeSession:
    def __init__(self, fail_commit: bool = False):
        self.fail_commit = fail_commit
        self.added = []
        self.rollback_called = False
        self.closed = False

    def add(self, item):
        self.added.append(item)

    def flush(self):
        return None

    def commit(self):
        if self.fail_commit:
            raise SQLAlchemyError("commit failed")

    def rollback(self):
        self.rollback_called = True

    def close(self):
        self.closed = True


def test_storage_writer_keeps_yaml_when_db_commit_succeeds(tmp_path, monkeypatch) -> None:
    session = _FakeSession()
    monkeypatch.setattr(doc_parser_workflow, "get_settings", lambda: _Settings(tmp_path))
    monkeypatch.setattr(doc_parser_workflow, "SessionLocal", lambda: session)

    result = doc_parser_workflow.storage_writer_node(_storage_state("TEST_STORAGE_OK"))

    final_path = tmp_path / "TEST_STORAGE_OK.yaml"
    assert result["yaml_path"] == str(final_path)
    assert final_path.exists()
    assert list(tmp_path.glob(".TEST_STORAGE_OK.*.tmp")) == []


def test_storage_writer_removes_only_current_yaml_when_db_commit_fails(tmp_path, monkeypatch) -> None:
    existing = tmp_path / "EXISTING_APPROVED.yaml"
    existing.write_text("keep: true\n", encoding="utf-8")
    session = _FakeSession(fail_commit=True)
    monkeypatch.setattr(doc_parser_workflow, "get_settings", lambda: _Settings(tmp_path))
    monkeypatch.setattr(doc_parser_workflow, "SessionLocal", lambda: session)

    result = doc_parser_workflow.storage_writer_node(_storage_state("TEST_STORAGE_FAIL"))

    assert result["yaml_path"] is None
    assert not (tmp_path / "TEST_STORAGE_FAIL.yaml").exists()
    assert list(tmp_path.glob(".TEST_STORAGE_FAIL.*.tmp")) == []
    assert existing.read_text(encoding="utf-8") == "keep: true\n"
    assert session.rollback_called is True
    assert any("YAML 산출물을 정리" in warning for warning in result["warnings"])


def test_storage_writer_does_not_overwrite_existing_yaml(tmp_path, monkeypatch) -> None:
    final_path = tmp_path / "TEST_STORAGE_EXISTS.yaml"
    final_path.write_text("approved: true\n", encoding="utf-8")
    monkeypatch.setattr(doc_parser_workflow, "get_settings", lambda: _Settings(tmp_path))
    monkeypatch.setattr(
        doc_parser_workflow,
        "SessionLocal",
        lambda: (_ for _ in ()).throw(AssertionError("DB should not be opened")),
    )

    result = doc_parser_workflow.storage_writer_node(_storage_state("TEST_STORAGE_EXISTS"))

    assert result["yaml_path"] is None
    assert final_path.read_text(encoding="utf-8") == "approved: true\n"
    assert any("이미 같은 policy_id 파일" in warning for warning in result["warnings"])


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
