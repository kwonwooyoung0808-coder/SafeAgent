from __future__ import annotations

import re
from typing import Any


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
