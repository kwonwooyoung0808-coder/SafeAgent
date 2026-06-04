from __future__ import annotations


class DocxChunkProcessor:
    """
    대형 문서를 섹션 단위로 분할 처리.

    qwen2.5:7b 안정 입력 크기(3000자) 기준.
    헤딩 기준 분할 → 초과 시 고정 크기 재분할.
    Phase 3-B: 청크 간 슬라이딩 윈도우 오버랩으로 경계 컨텍스트 손실 방지.
    Fix 5: 오버랩 추가 시 최종 청크가 MAX_CHARS_PER_CHUNK를 초과하지 않도록
    분할 단계에서 _EFFECTIVE_CHUNK_SIZE만큼만 자른다.
    청크별 결과를 중복 제거 후 병합.
    """

    MAX_CHARS_PER_CHUNK: int = 3000
    OVERLAP_CHARS: int = 200  # 이전 청크 끝 부분을 다음 청크 앞에 추가
    _OVERLAP_HEADER_LEN: int = 40  # "[이전 섹션 끝]\n...\n[현재 섹션 시작]\n" 길이 보정

    def split_by_headings(
        self,
        doc_structure: dict,
        raw_text: str,
        overlap_chars: int | None = None,
    ) -> list[dict]:
        """
        헤딩 기준으로 청크 분할.
        헤딩이 없으면 고정 크기 분할.
        개별 청크가 MAX_CHARS 초과 시 재분할.
        Phase 3-B: overlap_chars만큼 이전 청크 끝을 다음 청크 앞에 추가해
        조항 간 참조("제7조에서 언급한 내용은...") 컨텍스트 손실을 방지한다.

        Fix 5: 오버랩이 더해질 때 MAX_CHARS_PER_CHUNK를 초과하지 않도록
        원본 청크를 effective_size(= MAX - overlap - header)로 잘라 둔다.
        """
        _overlap = overlap_chars if overlap_chars is not None else self.OVERLAP_CHARS
        # Fix 5: 오버랩 후에도 MAX 한도를 지키도록 effective 크기 계산
        effective_size = max(
            500,
            self.MAX_CHARS_PER_CHUNK - _overlap - self._OVERLAP_HEADER_LEN,
        )

        headings = doc_structure.get("headings", [])

        if not headings:
            return self._apply_overlap(
                self._fixed_size_split(raw_text, effective_size),
                _overlap,
            )

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
            if len(chunk["text"]) > effective_size:
                subs = self._fixed_size_split(chunk["text"], effective_size)
                for j, sub in enumerate(subs):
                    result.append({
                        "section": f"{chunk['section']}_{j + 1}",
                        "level":   chunk["level"],
                        "text":    sub["text"],
                    })
            else:
                result.append(chunk)

        base = result if result else self._fixed_size_split(raw_text, effective_size)
        return self._apply_overlap(base, _overlap)

    def _apply_overlap(self, chunks: list[dict], overlap_chars: int) -> list[dict]:
        """각 청크 앞에 이전 청크의 마지막 overlap_chars 문자를 추가한다."""
        if overlap_chars <= 0 or len(chunks) <= 1:
            return chunks
        overlapped: list[dict] = [chunks[0]]
        for i in range(1, len(chunks)):
            prev_text = chunks[i - 1]["text"]
            tail = prev_text[-overlap_chars:] if len(prev_text) > overlap_chars else prev_text
            overlapped.append({
                **chunks[i],
                "text": f"[이전 섹션 끝]\n{tail}\n[현재 섹션 시작]\n{chunks[i]['text']}",
            })
        return overlapped

    def _fixed_size_split(self, text: str, size: int | None = None) -> list[dict]:
        chunk_size = size if size is not None else self.MAX_CHARS_PER_CHUNK
        return [
            {
                "section": f"section_{i // chunk_size + 1}",
                "level":   1,
                "text":    text[i: i + chunk_size],
            }
            for i in range(0, len(text), chunk_size)
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
