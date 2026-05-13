import json
import logging
import re
from functools import lru_cache
from pathlib import Path
import yaml
from src.core.config import get_settings
from src.schemas.judge import JudgeResult
from src.schemas.policy import Policy


logger = logging.getLogger(__name__)


# Phase 3-B: 프롬프트 템플릿은 deploy 시점에 고정되므로 process-lifetime LRU 적합.
# JudgeEngine 인스턴스가 매 호출마다 생성되어도 디스크 I/O 는 첫 호출 1회뿐.
@lru_cache(maxsize=32)
def _read_prompt_cached(absolute_path: str) -> str:
    """프롬프트 파일을 읽어 캐시. 키는 절대경로 문자열."""
    p = Path(absolute_path)
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8")


class JudgeEngine:
    """
    [Final Version]
    - 재시도 제한 로직 대응을 위한 신뢰도 설계
    - 심각도(Severity) 기반 차단 차등화 (Critical vs Warning)
    - LLM 장애 시나리오별 Fallback 전략 포함
    """
    def __init__(self, prompt_dir: str | None = None, llm_client=None):
        self.prompt_dir = Path(prompt_dir or get_settings().prompt_dir)
        self.llm_client = llm_client # 실제 연결 시 주입

    def _read_prompt(self, name: str) -> str:
        """프롬프트 파일(.txt, .yaml)을 읽어옵니다. Phase 3-B 부터 LRU 캐시 적용."""
        return _read_prompt_cached(str((self.prompt_dir / name).resolve()))

    def _get_filtered_few_shot(self, policy_id: str) -> str:
        """
        [PRD 최적화] 정책 ID에 맞는 Few-shot 예시만 필터링하여 프롬프트 크기를 줄이고 정확도를 높입니다.
        - CONTENT: 유해성 판정 예시
        - GROUND: 근거 기반 판정 예시
        - COMP: 형식 준수 판정 예시
        """
        full_content = self._read_prompt("few_shot_examples_v2.yaml")
        if not full_content:
            return ""

        try:
            data = yaml.safe_load(full_content)
            all_examples = data.get("examples", {})
            filtered_examples = {}

            # 정책 ID 접두어에 따른 예시 그룹 매칭
            if "CONTENT" in policy_id:
                target_key_prefix = "content_safety"
            elif "GROUND" in policy_id:
                target_key_prefix = "groundedness"
            elif "COMP" in policy_id:
                target_key_prefix = "instruction_compliance"
            else:
                target_key_prefix = "none"

            for key, val in all_examples.items():
                if key.startswith(target_key_prefix):
                    filtered_examples[key] = val

            if not filtered_examples:
                return "No relevant few-shot examples found."

            return yaml.dump({"examples": filtered_examples}, allow_unicode=True, sort_keys=False)
        except Exception:
            return "Error parsing few-shot examples."

    def _extract_judged_text(self, response: str) -> str:
        """
        [데이터 정규화] 응답이 JSON 형태인 경우 'answer' 필드의 본문만 추출하여 판정 대상을 명확히 합니다.
        """
        try:
            parsed = json.loads(response)
            if isinstance(parsed, dict):
                answer = parsed.get("answer")
                if isinstance(answer, str) and answer.strip():
                    return answer.strip()
        except json.JSONDecodeError:
            pass
        return response.strip()

    def _judge_groundedness_fallback(
        self,
        response: str,
        retrieved_context: list[str] | None,
    ) -> JudgeResult:
        """
        [B-4 대응] LLM 장애 시나리오를 위한 문자열 매칭 기반의 최소한의 Groundedness 판정 로직입니다.
        """
        judged_text = self._extract_judged_text(response)

        if not retrieved_context:
            return JudgeResult(
                verdict="FAIL",
                confidence=0.65,
                reason="No retrieved context was provided.",
                evidence_text=judged_text[:120] or None,
            )

        cleaned_context = [str(item).strip() for item in retrieved_context if str(item).strip()]
        if not cleaned_context:
            return JudgeResult(
                verdict="FAIL",
                confidence=0.65,
                reason="No meaningful retrieved context was provided.",
                evidence_text=judged_text[:120] or None,
            )

        context_text = " ".join(cleaned_context)
        # 단순 포함 여부 확인 (LLM 연결 전 임시 로직)
        if judged_text and judged_text in context_text:
            return JudgeResult(
                verdict="PASS",
                confidence=0.9,
                reason="The response is grounded in the provided context.",
                evidence_text=None,
            )

        return JudgeResult(
            verdict="FAIL",
            confidence=0.72,
            reason="The response is not sufficiently grounded in the provided context.",
            evidence_text=judged_text[:120] or None,
        )

    def _parse_llm_json_result(self, raw_llm_output: str) -> JudgeResult:
        """LLM 출력에서 JSON 부분 추출. 항상 JudgeResult 반환 — 파싱 실패 시
        보수적 FAIL 로 처리해 호출자가 None 체크/raise 할 필요 없음.

        지원 포맷:
        - 순수 JSON
        - 앞뒤 설명 문구 + JSON
        - ```json ... ``` 마크다운 코드 블록
        - ``` ... ``` 일반 코드 블록
        """
        if not raw_llm_output or not raw_llm_output.strip():
            return JudgeResult(
                verdict="FAIL",
                confidence=0.0,
                reason="LLM이 빈 응답을 반환했습니다.",
                evidence_text=None,
            )

        # ① 마크다운 코드 블록 제거 (```json ... ``` 또는 ``` ... ```)
        cleaned = re.sub(r"```(?:json)?\s*", "", raw_llm_output, flags=re.IGNORECASE)
        cleaned = cleaned.replace("```", "")

        # ② 가장 바깥쪽 { } 구간 추출
        json_match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not json_match:
            return JudgeResult(
                verdict="FAIL",
                confidence=0.0,
                reason="LLM 응답에서 JSON 구조를 찾지 못함",
                evidence_text=raw_llm_output[:200] or None,
            )

        try:
            parsed_result = json.loads(json_match.group())
            return JudgeResult(**parsed_result)
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            return JudgeResult(
                verdict="FAIL",
                confidence=0.0,
                reason=f"JSON 파싱 실패: {type(e).__name__}: {e}",
                evidence_text=raw_llm_output[:200] or None,
            )

    def _determine_action_by_severity(self, result: JudgeResult, policy_id: str) -> JudgeResult:
        """
        [PRD B-1 반영] 판정 결과와 정책 성격에 따라 Severity와 Action을 결정합니다.
        Action 유형: Block(즉시 차단), Warn(경고 후 노출), Retry(교정 시도), Allow(통과)
        """
        # 1. 보안/유해성 정책 (CONTENT) 위반 시 -> 무조건 Critical & Block
        if result.verdict == "FAIL" and "CONTENT" in policy_id:
            result.severity = "Critical"
            result.action = "Block"
            result.reason = f"[보안 정책 위반] {result.reason}"

        # 2. 사실 근거 정책 (GROUND) 위반 시
        elif result.verdict == "FAIL" and "GROUND" in policy_id:
            # 신뢰도가 매우 낮으면 할루시네이션으로 판단하여 차단
            if result.confidence < 0.6:
                result.severity = "Critical"
                result.action = "Block"
                result.reason = f"[신뢰도 저하로 인한 차단] {result.reason}"
            # 신뢰도가 중간 정도라면 교정을 위해 재시도 유도하거나 경고 노출
            else:
                result.severity = "Warning"
                result.action = "Retry" # LangGraph에서 재시도 횟수 차감 후 루프
                result.reason = f"[근거 확인 필요] {result.reason}"

        # 3. 형식 준수 정책 (COMP) 위반 시
        elif result.verdict == "FAIL" and "COMP" in policy_id:
            result.severity = "Warning"
            result.action = "Retry" # 형식이 틀린 경우 웬만하면 다시 생성 시킴

        # 4. 정상 판정 (PASS)
        else:
            result.severity = "Safe"
            result.action = "Allow"
            
        return result

    def judge(
        self,
        policy: Policy,
        response: str,
        retrieved_context: list[str] | None,
        query: str = "",
        current_retry: int = 0  # LangGraph에서 전달받은 현재 재시도 횟수
    ) -> JudgeResult:
        """
        Main 판정 엔진: LLM 호출 -> 파싱 -> 심각도 판단 -> 최종 액션 결정
        """
        # [생략] 1. 프롬프트 조립 로직 (이전과 동일)
        system_tmpl = self._read_prompt("system_judge_v2.txt")
        cot_tmpl = self._read_prompt("cot_reasoning_v2.txt")
        few_shot_str = self._get_filtered_few_shot(policy.id)
        rendered_prompt = f"{system_tmpl}\n\n{cot_tmpl}\n\n{few_shot_str}".format(
            user_query=query,
            retrieved_context="\n".join(retrieved_context) if retrieved_context else "N/A",
            assistant_response=response,
            criteria=policy.judge.criteria
        )

        # 2. LLM 호출 및 에러 처리
        llm_unavailable = False
        try:
            if self.llm_client:
                raw_llm_output = self.llm_client.generate(rendered_prompt)
            else:
                raw_llm_output = None
                llm_unavailable = True
        except Exception as e:
            logger.exception("Governance judge LLM call failed: %s", e)
            raw_llm_output = None
            llm_unavailable = True

        # 3. LLM 자체가 없거나 실패한 경우 → 정책별 Fallback
        # (파서가 빈 입력에도 JudgeResult(FAIL) 을 반환하므로 별도 분기 필요)
        if llm_unavailable or not raw_llm_output:
            if policy.id == "GROUND_001":
                parsed_result = self._judge_groundedness_fallback(response, retrieved_context)
            else:
                logger.warning("Judge LLM unavailable; semantic check skipped for policy_id=%s", policy.id)
                parsed_result = JudgeResult(
                    verdict="PASS",
                    confidence=0.5,
                    reason="Judge LLM unavailable; semantic check skipped.",
                )
        else:
            parsed_result = self._parse_llm_json_result(raw_llm_output)

        # 5. [신규] 심각도 기반 최종 액션 결정
        final_result = self._determine_action_by_severity(parsed_result, policy.id)

        # 6. [신규] 재시도 횟수 초과 시 강제 차단 처리
        if final_result.action == "Retry" and current_retry >= 3:
            final_result.action = "Block"
            final_result.reason = "[최종 실패] 3회 재시도 후에도 기준을 만족하지 못했습니다."
            final_result.severity = "Critical"

        return final_result
