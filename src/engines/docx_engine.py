from __future__ import annotations

from dataclasses import dataclass, field

from src.engines.text_sanitizer import TextSanitizer


@dataclass
class DocxParseResult:
    raw_text:           str
    raw_tables:         list[list[list[str]]]
    doc_structure:      dict
    warnings:           list[str] = field(default_factory=list)
    injection_detected: bool      = False


class DocxEngine:
    """
    python-docx 기반 .docx 파싱 엔진.

    보안:
    - 흰색 폰트(FFFFFF) / vanish 속성의 숨겨진 텍스트 필터링
    - TextSanitizer로 프롬프트 인젝션 패턴 이스케이프 처리

    반환 텍스트는 원본이 아닌 이스케이프된 sanitized_text.
    """

    def parse(self, file_path: str) -> DocxParseResult:
        from docx import Document as DocxDocument

        doc = DocxDocument(file_path)
        raw_text = ""
        doc_structure: dict = {"headings": [], "tables": []}

        for para in doc.paragraphs:
            if self._is_hidden(para):
                continue
            if para.text.strip():
                if "Heading" in para.style.name:
                    level = (
                        int(para.style.name[-1])
                        if para.style.name[-1].isdigit()
                        else 1
                    )
                    doc_structure["headings"].append(
                        {"level": level, "text": para.text}
                    )
                raw_text += para.text + "\n"

        raw_tables: list[list[list[str]]] = []
        for table in doc.tables:
            tbl = [
                [cell.text.strip() for cell in row.cells]
                for row in table.rows
            ]
            raw_tables.append(tbl)
            doc_structure["tables"].append(tbl)

        sanitizer = TextSanitizer()
        sanitized_text, injections = sanitizer.sanitize(raw_text)

        warnings: list[str] = list(injections)
        injection_detected = bool(injections)

        return DocxParseResult(
            raw_text=sanitized_text,
            raw_tables=raw_tables,
            doc_structure=doc_structure,
            warnings=warnings,
            injection_detected=injection_detected,
        )

    @staticmethod
    def _is_hidden(para) -> bool:
        """흰색 폰트(FFFFFF) 또는 OOXML vanish 속성의 숨겨진 텍스트 탐지."""
        NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
        for run in para.runs:
            try:
                if run.font.color and run.font.color.type is not None:
                    if str(run.font.color.rgb).upper() in ("FFFFFF", "FFFFFE"):
                        return True
            except Exception:
                pass
            if run._element.find(f".//{{{NS}}}vanish") is not None:
                return True
        return False
