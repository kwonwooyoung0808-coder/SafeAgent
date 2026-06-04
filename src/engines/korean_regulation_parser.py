from __future__ import annotations

import re
from typing import Any

# ── 금지 표현 추출 패턴 ──────────────────────────────────────────────────
# 한국 기업 내규에서 "X를 금지한다", "X를 하여서는 안 된다" 형태의 금지 표현에서
# 금지 대상 명사구를 추출하기 위한 정규식 패턴들.
_PROHIBITION_VERB_RE = re.compile(
    r"(금지|불허|제한|차단|하여서는\s*안|해서는\s*안|아니\s*된|아니한|불가|금한)"
)

# 「」 또는 "..." 로 명시된 금지어 추출
_BRACKET_TERM_RE  = re.compile(r"「([^」]{1,30})」")
_QUOTE_TERM_RE    = re.compile(r'"([^"]{2,30})"')
_SINGLE_QUOTE_RE  = re.compile(r"'([^']{2,20})'")

# Fix 8: 「」 따옴표를 포함하여 "임직원은 「영업비밀」을 ... 금지한다" 패턴까지 매칭
# 단, 매칭 결과에서 「」를 자체 제거하는 후처리 로직 추가.
_OBJECT_BEFORE_VERB_RE = re.compile(
    r"([가-힣a-zA-Z0-9\s,，、··「」\"']{2,50})"
    r"(?:을|를|은|는|이|가)\s*"
    r"(?:금지|불허|제한|하여서는\s*안|해서는\s*안|아니\s*된)"
)


def _clean_extracted_term(raw: str) -> str:
    """매칭된 raw 문자열에서 핵심 명사구만 정제."""
    # 「」 외부 제거: "임직원은 「영업비밀」" → "영업비밀"
    bracket_match = re.search(r"「([^」]+)」", raw)
    if bracket_match:
        return bracket_match.group(1).strip()
    # 따옴표 외부 제거
    quote_match = re.search(r'"([^"]+)"', raw)
    if quote_match:
        return quote_match.group(1).strip()
    # "임직원은 영업비밀" 같은 케이스 — 주어 제거 (마지막 명사구만)
    # 공백으로 분리해 마지막 토큰 활용
    parts = re.split(r"[\s,，、]+", raw.strip())
    if parts:
        # 너무 짧은 토큰(주어) 건너뛰고 가장 긴 명사구 선택
        candidates = [p for p in parts if 2 <= len(p) <= 20]
        if candidates:
            return max(candidates, key=len).strip()
    return raw.strip()[:20]


def extract_forbidden_terms_from_articles(articles: list[dict[str, Any]]) -> list[str]:
    """
    한국식 조문 articles 리스트에서 규칙 기반으로 금지어 후보를 추출한다.

    탐지 전략 (우선순위 순):
    1. 「」 또는 "" 로 명시된 명사구 (가장 신뢰도 높음)
    2. "X를 금지한다" 패턴 앞의 목적어 명사구
    3. 금지 조문의 clause/subclause 텍스트에서 동사구 앞 명사구 추출
       (Fix 4: 기존 LIST_ITEM_RE는 KoreanRegulationParser가 이미 prefix를
       제거해놓기 때문에 매칭 안 됨 — clause["text"]를 직접 처리)
    """
    candidates: list[str] = []
    seen: set[str] = set()

    def _add(term: str) -> None:
        term = term.strip().strip(".,。·「」\"'")
        if 2 <= len(term) <= 25 and term not in seen:
            candidates.append(term)
            seen.add(term)

    for article in articles:
        source = article.get("source_text", "")
        if not source:
            continue

        # 전략 1: 괄호/따옴표 명시 금지어
        for m in _BRACKET_TERM_RE.finditer(source):
            _add(m.group(1))
        for m in _QUOTE_TERM_RE.finditer(source):
            _add(m.group(1))
        for m in _SINGLE_QUOTE_RE.finditer(source):
            _add(m.group(1))

        # 전략 2: "X를 금지한다" 패턴 — 금지 동사가 있는 조문만 처리
        if _PROHIBITION_VERB_RE.search(source):
            for m in _OBJECT_BEFORE_VERB_RE.finditer(source):
                raw = m.group(1)
                # 쉼표로 나열된 경우 분리해 각각 정제
                for part in re.split(r"[,，、]", raw):
                    cleaned = _clean_extracted_term(part)
                    if cleaned:
                        _add(cleaned)

        # 전략 3: Fix 4 — clause["text"]는 이미 prefix가 제거된 본문이므로
        # 직접 분석. 금지 조문 내부의 각 항목에서 금지 대상 명사구 추출.
        if _PROHIBITION_VERB_RE.search(source):
            for clause in article.get("clauses", []):
                txt = clause.get("text", "")
                if not txt:
                    continue
                # 동사구("~하는 행위", "~사용", "~제공") 앞 명사구만 분리
                head = re.split(
                    r"(?:하는|하거나|이용한|사용한|포함한|제공한|반출|유출|공개)\s*",
                    txt,
                    maxsplit=1,
                )[0].strip()
                if 2 <= len(head) <= 25:
                    # 「」 명시 우선
                    bracket_match = _BRACKET_TERM_RE.search(head)
                    if bracket_match:
                        _add(bracket_match.group(1))
                    else:
                        _add(head)

    return candidates


_CHAPTER_RE = re.compile(r"^제\s*(?P<number>[0-9]+|[일이삼사오육칠팔구십백천]+)\s*장\s*(?P<title>.*)$")
_ARTICLE_RE = re.compile(
    r"^제\s*(?P<number>[0-9]+|[일이삼사오육칠팔구십백천]+)\s*조\s*"
    r"(?:\((?P<title>[^)]*)\))?\s*(?P<body>.*)$"
)
_CLAUSE_RE = re.compile(r"^(?P<number>[0-9]+)\.\s*(?P<body>.+)$")
_SUBCLAUSE_RE = re.compile(r"^(?P<number>[가-하])\.\s*(?P<body>.+)$")


class KoreanRegulationParser:
    """한국식 사규/내규 조문 구조를 검토 가능한 JSON 형태로 정규화한다."""

    def parse(self, blocks: list[dict[str, Any]]) -> dict[str, Any]:
        document: dict[str, Any] = {
            "title": None,
            "preamble": [],
            "chapters": [],
            "articles": [],
            "tables": [],
        }
        current_chapter: dict[str, Any] | None = None
        current_article: dict[str, Any] | None = None
        current_clause: dict[str, Any] | None = None

        for block_index, block in enumerate(blocks):
            if block.get("type") == "table":
                table_info = {
                    "block_index": block_index,
                    "rows": block.get("rows", []),
                    "text": block.get("text", ""),
                    "source_article": current_article.get("article_no") if current_article else None,
                }
                document["tables"].append(table_info)
                if current_article is not None:
                    current_article.setdefault("tables", []).append(table_info)
                continue

            text = (block.get("text") or "").strip()
            if not text:
                continue

            chapter_match = _CHAPTER_RE.match(text)
            if chapter_match:
                current_chapter = {
                    "chapter_no": chapter_match.group("number"),
                    "title": chapter_match.group("title").strip() or None,
                    "heading": text,
                    "articles": [],
                    "block_index": block_index,
                }
                document["chapters"].append(current_chapter)
                current_article = None
                current_clause = None
                continue

            article_match = _ARTICLE_RE.match(text)
            if article_match:
                body = article_match.group("body").strip()
                current_article = {
                    "article_no": article_match.group("number"),
                    "title": article_match.group("title") or None,
                    "heading": text,
                    "paragraphs": [body] if body else [],
                    "clauses": [],
                    "tables": [],
                    "source_text": text,
                    "block_index": block_index,
                }
                document["articles"].append(current_article)
                if current_chapter is not None:
                    current_chapter["articles"].append(current_article)
                current_clause = None
                continue

            clause_match = _CLAUSE_RE.match(text)
            if clause_match and current_article is not None:
                current_clause = {
                    "clause_no": clause_match.group("number"),
                    "text": clause_match.group("body").strip(),
                    "subclauses": [],
                    "block_index": block_index,
                }
                current_article["clauses"].append(current_clause)
                current_article["source_text"] += "\n" + text
                continue

            subclause_match = _SUBCLAUSE_RE.match(text)
            if subclause_match and current_clause is not None:
                current_clause["subclauses"].append({
                    "subclause_no": subclause_match.group("number"),
                    "text": subclause_match.group("body").strip(),
                    "block_index": block_index,
                })
                if current_article is not None:
                    current_article["source_text"] += "\n" + text
                continue

            if current_article is not None:
                current_article["paragraphs"].append(text)
                current_article["source_text"] += "\n" + text
            elif document["title"] is None:
                document["title"] = text
            else:
                document["preamble"].append(text)

        document["stats"] = {
            "block_count": len(blocks),
            "chapter_count": len(document["chapters"]),
            "article_count": len(document["articles"]),
            "table_count": len(document["tables"]),
        }
        return document


def regulation_to_llm_context(regulation: dict[str, Any], max_articles: int = 80) -> str:
    """LLM 입력용으로 조문 구조를 간결한 텍스트로 직렬화한다."""
    lines: list[str] = []
    title = regulation.get("title")
    if title:
        lines.append(f"[문서 제목] {title}")

    for article in regulation.get("articles", [])[:max_articles]:
        lines.append("")
        article_title = article.get("title") or ""
        lines.append(f"[제{article.get('article_no')}조 {article_title}]")
        for paragraph in article.get("paragraphs", []):
            if paragraph:
                lines.append(paragraph)
        for clause in article.get("clauses", []):
            lines.append(f"{clause.get('clause_no')}. {clause.get('text')}")
            for sub in clause.get("subclauses", []):
                lines.append(f"  {sub.get('subclause_no')}. {sub.get('text')}")
        for table in article.get("tables", []):
            if table.get("text"):
                lines.append(f"[표] {table['text']}")

    return "\n".join(lines).strip()
