from __future__ import annotations


class DocxChunkProcessor:
    """
    대형 문서를 섹션 단위로 분할 처리.

    qwen2.5:7b 안정 입력 크기(3000자) 기준.
    헤딩 기준 분할 → 초과 시 고정 크기 재분할.
    청크별 결과를 중복 제거 후 병합.
    """

    MAX_CHARS_PER_CHUNK: int = 3000

    def split_by_headings(
        self,
        doc_structure: dict,
        raw_text: str,
    ) -> list[dict]:
        """
        헤딩 기준으로 청크 분할.
        헤딩이 없으면 고정 크기 분할.
        개별 청크가 MAX_CHARS 초과 시 재분할.
        """
        headings = doc_structure.get("headings", [])

        if not headings:
            return self._fixed_size_split(raw_text)

        raw_chunks: list[dict] = []
        for i, heading in enumerate(headings):
            start_idx = raw_text.find(heading["text"])
            if start_idx == -1:
                continue
            end_idx = (
                raw_text.find(headings[i + 1]["text"])
                if i + 1 < len(headings)
                else len(raw_text)
            )
            chunk_text = raw_text[start_idx:end_idx].strip()
            if chunk_text:
                raw_chunks.append({
                    "section": heading["text"],
                    "level":   heading["level"],
                    "text":    chunk_text,
                })

        result: list[dict] = []
        for chunk in raw_chunks:
            if len(chunk["text"]) > self.MAX_CHARS_PER_CHUNK:
                subs = self._fixed_size_split(chunk["text"])
                for j, sub in enumerate(subs):
                    result.append({
                        "section": f"{chunk['section']}_{j + 1}",
                        "level":   chunk["level"],
                        "text":    sub["text"],
                    })
            else:
                result.append(chunk)

        return result if result else self._fixed_size_split(raw_text)

    def _fixed_size_split(self, text: str) -> list[dict]:
        return [
            {
                "section": f"section_{i // self.MAX_CHARS_PER_CHUNK + 1}",
                "level":   1,
                "text":    text[i: i + self.MAX_CHARS_PER_CHUNK],
            }
            for i in range(0, len(text), self.MAX_CHARS_PER_CHUNK)
        ]

    def merge_results(self, chunk_results: list[dict]) -> dict:
        """
        청크별 파싱 결과 병합.
        - forbidden_words: 소문자 기준 중복 제거
        - compliance_checks: ID 재부여 (청크 간 ID 충돌 방지)
        - actions: BLOCK > FLAGGED > LOG 우선순위로 가장 엄격한 값 선택
        - warnings: 전부 수집
        """
        merged: dict = {
            "forbidden_words":   [],
            "compliance_checks": [],
            "actions":           {},
            "warnings":          [],
        }
        seen_words: set[str] = set()
        check_counter = 1

        for result in chunk_results:
            for word in result.get("forbidden_words", []):
                if word.lower() not in seen_words:
                    merged["forbidden_words"].append(word)
                    seen_words.add(word.lower())

            for check in result.get("compliance_checks", []):
                merged["compliance_checks"].append(
                    {**check, "id": f"CC-{check_counter:03d}"}
                )
                check_counter += 1

            for key, val in result.get("actions", {}).items():
                merged["actions"][key] = self._stricter_action(
                    merged["actions"].get(key), val
                )

            merged["warnings"].extend(result.get("warnings", []))

        return merged

    @staticmethod
    def _stricter_action(a: str | None, b: str) -> str:
        """BLOCK > FLAGGED > LOG 순으로 더 엄격한 값 선택."""
        rank = {"BLOCK": 3, "FLAGGED": 2, "LOG": 1}
        if a is None:
            return b
        return a if rank.get(a, 0) >= rank.get(b, 0) else b
