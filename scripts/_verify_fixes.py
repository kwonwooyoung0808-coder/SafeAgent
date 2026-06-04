"""수정사항 검증 스크립트 — Phase 0~4 핵심 로직 회귀 테스트."""
from __future__ import annotations

import sys
from pathlib import Path

# UTF-8 강제 (Windows cp949 콘솔 대응)
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent.parent))


def section(title: str) -> None:
    print()
    print("=" * 60)
    print(f"  {title}")
    print("=" * 60)


# ── Phase 1-A: 규칙 기반 금지어 추출 ────────────────────────────
section("Phase 1-A / Fix 4 / Fix 8: extract_forbidden_terms_from_articles")

from src.engines.korean_regulation_parser import extract_forbidden_terms_from_articles

cases = [
    {
        "label": "「」 명시 금지어",
        "articles": [{
            "article_no": "3",
            "source_text": "제3조(금지사항) 임직원은 「영업비밀」, 「내부자료」, 「고객정보」를 외부에 유출하여서는 안된다.",
            "clauses": [],
        }],
        "must_have": ["영업비밀", "내부자료", "고객정보"],
    },
    {
        "label": "따옴표 + 금지 동사",
        "articles": [{
            "article_no": "4",
            "source_text": '다음 표현의 사용을 금지한다: "횡령", "배임", "뇌물".',
            "clauses": [],
        }],
        "must_have": ["횡령", "배임", "뇌물"],
    },
    {
        "label": "Fix 4 — clause 텍스트 (prefix 이미 제거됨)",
        "articles": [{
            "article_no": "5",
            "source_text": "제5조(금지사항) 다음 각 호의 행위를 금지한다.",
            "clauses": [
                {"clause_no": "1", "text": "「영업비밀」을 경쟁사에 제공하는 행위", "subclauses": []},
                {"clause_no": "2", "text": "「내부 문건」을 무단으로 외부 반출하는 행위", "subclauses": []},
            ],
        }],
        "must_have": ["영업비밀", "내부 문건"],
    },
    {
        "label": "Fix 8 — 「」 포함 OBJECT_BEFORE_VERB 패턴",
        "articles": [{
            "article_no": "6",
            "source_text": "임직원은 「기술자료」를 외부에 공개하여서는 안 된다.",
            "clauses": [],
        }],
        "must_have": ["기술자료"],
    },
]

fails = []
for case in cases:
    result = extract_forbidden_terms_from_articles(case["articles"])
    missing = [w for w in case["must_have"] if w not in result]
    status = "PASS" if not missing else f"FAIL (missing: {missing})"
    print(f"  [{status}] {case['label']}")
    print(f"          추출: {result}")
    if missing:
        fails.append(case["label"])

if fails:
    print(f"\n  FAILED: {fails}")
else:
    print("\n  ALL PASS")


# ── Phase 3-C / Fix 3: GroundingValidator 형태소 ────────────────
section("Fix 3: GroundingValidator (어근 최소 길이 4자)")

from src.engines.grounding_validator import GroundingValidator

v = GroundingValidator()
text = "임직원은 영업비밀을 보호해야 한다. 정보보안 교육을 받는다."

tests_3 = [
    ("정확 일치",          v._word_in_text("영업비밀", text),    True),
    ("4자 복합어 매칭",     v._word_in_text("정보보안", text),    True),
    ("없는 단어 거부",      v._word_in_text("XYZ를", "오늘 좋은 날"), False),
    ("bare noun + suffix", v._word_in_text("영업비밀", "영업비밀을 누설"), True),
]
for label, got, expected in tests_3:
    status = "PASS" if got == expected else "FAIL"
    print(f"  [{status}] {label}: got={got}, expected={expected}")

verified, hallucinated = v.validate_forbidden_words(
    ["영업비밀", "정보보안", "존재하지않는단어", "횡령"], text
)
print(f"  verified={verified}")
print(f"  hallucinated={hallucinated}")
ok = (
    "영업비밀" in verified
    and "정보보안" in verified
    and "존재하지않는단어" in hallucinated
    and "횡령" in hallucinated
)
print(f"  [{'PASS' if ok else 'FAIL'}] validate_forbidden_words 통합")


# ── Fix 5: 청크 크기 사전 조정 ──────────────────────────────────
section("Fix 5: 청크 크기 사전 조정 (오버랩 후에도 MAX 이하)")

from src.engines.docx_chunk_processor import DocxChunkProcessor

p = DocxChunkProcessor()
MAX = p.MAX_CHARS_PER_CHUNK

long_text = "한국기업내규" * 2000  # 약 12000자
chunks = p.split_by_headings({}, long_text)
print(f"  분할 결과: {len(chunks)}개 청크")
overflows = [(i, len(c["text"])) for i, c in enumerate(chunks) if len(c["text"]) > MAX]
if overflows:
    print(f"  [FAIL] {len(overflows)}개 청크가 MAX({MAX}) 초과: {overflows}")
else:
    sizes = [len(c["text"]) for c in chunks]
    print(f"  청크 크기 분포: min={min(sizes)}, max={max(sizes)}, MAX={MAX}")
    print("  [PASS] 모든 청크가 MAX 이하")


# ── Phase 1-D: _has_forbidden_words + _yaml_needs_review ─────
section("Phase 1-D: 보류 조건 분리")

from src.routers.policy_compiler import _has_forbidden_words, _yaml_needs_review

# Case 1: forbidden_words 있음 + judge.criteria에 needs_review 텍스트 → 활성화 허용
yaml_with_fw = """
id: TEST_1
rules:
  - condition: contains_categorized_forbidden_terms
    parameters:
      categories:
        custom_policy_terms:
          enabled: true
          exact_terms: ["영업비밀", "내부자료"]
judge:
  enabled: true
  criteria: |
    검토 필요: true
    - [CC-001] 조항 검토
"""
import yaml as pyaml
parsed = pyaml.safe_load(yaml_with_fw)
has_fw = _has_forbidden_words(parsed)
needs_review = _yaml_needs_review(yaml_with_fw, parsed)
print(f"  Case 1 (forbidden_words O + judge needs_review): has_fw={has_fw}, needs_review={needs_review}")
print(f"  [{'PASS' if has_fw and not needs_review else 'FAIL'}] forbidden_words 있으면 활성화 허용")

# Case 2: forbidden_words 없음 + needs_review 텍스트 → 활성화 차단
yaml_no_fw = """
id: TEST_2
rules:
  - condition: contains_categorized_forbidden_terms
    parameters:
      categories:
        custom_policy_terms:
          enabled: false
          exact_terms: []
judge:
  enabled: true
  criteria: |
    검토 필요: true
"""
parsed2 = pyaml.safe_load(yaml_no_fw)
has_fw2 = _has_forbidden_words(parsed2)
needs_review2 = _yaml_needs_review(yaml_no_fw, parsed2)
print(f"  Case 2 (forbidden_words X + needs_review): has_fw={has_fw2}, needs_review={needs_review2}")
print(f"  [{'PASS' if not has_fw2 and needs_review2 else 'FAIL'}] forbidden_words 없으면 차단")


# ── Phase 2-A: Ollama JSON Schema 파라미터 시그니처 ─────────────
section("Phase 2-A: OllamaClient.chat() json_schema 파라미터")

import inspect
from src.services.ollama_client import OllamaClient

sig = inspect.signature(OllamaClient.chat)
params = list(sig.parameters.keys())
has_param = "json_schema" in params
print(f"  chat() 파라미터: {params}")
print(f"  [{'PASS' if has_param else 'FAIL'}] json_schema 파라미터 존재")


# ── Phase 2-B: 재시도 로직 (Fix 2) ──────────────────────────────
section("Fix 2: Step 2 재시도 시 temperature 변화")

import src.engines.doc_parser_engine as dpe
src_text = Path("src/engines/doc_parser_engine.py").read_text(encoding="utf-8")
has_retry_temps = "retry_temperatures" in src_text and "[0.0, 0.15, 0.3]" in src_text
has_retry_hints = "retry_hints" in src_text and "재시도" in src_text
print(f"  retry_temperatures 정의: {'YES' if has_retry_temps else 'NO'}")
print(f"  retry_hints 정의: {'YES' if has_retry_hints else 'NO'}")
print(f"  [{'PASS' if has_retry_temps and has_retry_hints else 'FAIL'}] Fix 2 적용 확인")


# ── Phase 4-B: 메트릭 컬럼 ──────────────────────────────────────
section("Phase 4-B: PolicyConversionLogModel 메트릭 컬럼")

from src.database.models import PolicyConversionLogModel
cols = {c.name for c in PolicyConversionLogModel.__table__.columns}
needed = ["total_latency_ms", "llm_call_count", "chunk_count", "hallucination_removals_count"]
for n in needed:
    print(f"  [{'PASS' if n in cols else 'FAIL'}] {n}")


# ── Fix 1: 메트릭 카운터 증가 로직 ───────────────────────────────
section("Fix 1: 워크플로우 메트릭 카운터 증가")

wf_src = Path("src/workflows/doc_parser_workflow.py").read_text(encoding="utf-8")
checks = [
    ("llm_call_count += 1",        "금지어 LLM 호출 +1"),
    ("llm_call_count += 2",        "Step1+Step2 +2"),
    ("llm_call_count += chunk_count * 2", "청크별 +2"),
    ("chunk_count = len(chunks)",  "청크 수 기록"),
    ("hallucination_count += len(hallucinated)", "환각 제거 수 +N"),
]
for needle, label in checks:
    found = needle in wf_src
    print(f"  [{'PASS' if found else 'FAIL'}] {label}: '{needle}'")


print()
print("=" * 60)
print("  ALL VERIFICATION CHECKS COMPLETE")
print("=" * 60)
