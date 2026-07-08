import pytest
from sqlalchemy.exc import SQLAlchemyError

from src.workflows import doc_parser_workflow


@pytest.mark.asyncio
async def test_korean_regulation_draft_skips_full_two_step_parse(monkeypatch) -> None:
    """
    한국식 조문 감지 시 무거운 2-step LLM full parse는 건너뛴다.
    (Fix 7: 규칙 기반 결과가 임계값 미만일 때만 금지어 전용 경량 LLM 호출.)
    """
    async def fail_if_called(*args, **kwargs):
        raise AssertionError(
            "Full 2-step LLM parse should not be called for structured Korean regulations"
        )

    async def fake_forbidden_llm(text, client=None):
        # 경량 금지어 호출만 허용 — 빈 결과 반환해 LLM 미작동 환경 시뮬레이션
        return [], []

    monkeypatch.setattr(doc_parser_workflow, "run_two_step_llm_parse", fail_if_called)
    monkeypatch.setattr(doc_parser_workflow, "_extract_forbidden_words_llm", fake_forbidden_llm)

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
    # 새 로직: draft 변환 메시지 또는 LLM 보강 메시지가 있어야 함
    assert any(
        ("규칙 기반" in warning) or ("draft" in warning) or ("구조화" in warning)
        for warning in result["warnings"]
    )


def test_grounding_removal_is_reflected_in_serialized_yaml() -> None:
    """
    #16 회귀 방지: 환각 금지어가 grounding 검증으로 제거되면, 직렬화된
    yaml_content 에도 반드시 반영되어야 한다.

    버그 당시: yaml_serializer 가 schema_validator(grounding) 보다 먼저 실행되어
    제거된 환각 금지어가 실제 YAML/스냅샷에 그대로 남았다. 노드 순서를
    grounding_validator → yaml_serializer 로 바꿔 해결.
    """
    raw_text = "제1조(금지사항) 임직원은 「영업비밀」을 외부에 유출하여서는 안 된다."
    # LLM 이 원본에 없는 "대외비"를 환각으로 추출했다고 가정.
    state = {
        "policy_id": "TEST_GROUNDING_YAML",
        "policy_name": "Grounding YAML Policy",
        "raw_text": raw_text,
        "extracted_rules": {
            "forbidden_words": ["영업비밀", "대외비"],  # "대외비"는 원본 미존재
            "compliance_checks": [],
            "actions": {},
        },
        "warnings": [],
    }

    grounded = doc_parser_workflow.grounding_validator_node(state)
    # 환각 단어는 extracted_rules 에서 제거됨
    assert "대외비" not in grounded["extracted_rules"]["forbidden_words"]
    assert "영업비밀" in grounded["extracted_rules"]["forbidden_words"]
    assert grounded["hallucination_removals_count"] == 1

    # 정제된 규칙으로 직렬화 → yaml_content 에 환각 단어가 없어야 함
    serialized = doc_parser_workflow.yaml_serializer_node({**state, **grounded})
    assert "대외비" not in serialized["yaml_content"]
    assert "영업비밀" in serialized["yaml_content"]


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
