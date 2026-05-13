from src.engines.korean_regulation_parser import (
    KoreanRegulationParser,
    regulation_to_llm_context,
)


def test_korean_regulation_parser_extracts_chapters_articles_and_clauses():
    blocks = [
        {"type": "paragraph", "text": "시스템 보안규정"},
        {"type": "paragraph", "text": "제1장 총칙"},
        {"type": "paragraph", "text": "제1조(목적) 회사의 보안을 관리한다."},
        {"type": "paragraph", "text": "1. 시스템관리자는 접근권한을 관리하여야 한다."},
        {"type": "paragraph", "text": "가. 불필요한 권한은 삭제한다."},
        {"type": "table", "rows": [["구분", "내용"], ["점검", "월 1회"]], "text": "구분 | 내용\n점검 | 월 1회"},
    ]

    result = KoreanRegulationParser().parse(blocks)

    assert result["title"] == "시스템 보안규정"
    assert result["stats"]["chapter_count"] == 1
    assert result["stats"]["article_count"] == 1
    assert result["articles"][0]["article_no"] == "1"
    assert result["articles"][0]["title"] == "목적"
    assert result["articles"][0]["clauses"][0]["clause_no"] == "1"
    assert result["articles"][0]["clauses"][0]["subclauses"][0]["subclause_no"] == "가"
    assert result["tables"][0]["source_article"] == "1"


def test_regulation_to_llm_context_includes_source_article_text():
    regulation = KoreanRegulationParser().parse([
        {"type": "paragraph", "text": "영업비밀 관리규정"},
        {"type": "paragraph", "text": "제7조(관리) 영업비밀은 관리대장에 기록한다."},
    ])

    context = regulation_to_llm_context(regulation)

    assert "[문서 제목] 영업비밀 관리규정" in context
    assert "[제7조 관리]" in context
    assert "영업비밀은 관리대장에 기록한다" in context
