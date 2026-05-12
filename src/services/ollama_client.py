from __future__ import annotations

import re

import httpx

from src.core.config import get_settings

# qwen3 / deepseek-r1 등 thinking-mode 모델은 응답 앞에 <think>...</think> 블록을
# 출력해 JudgeEngine JSON 파서를 깨뜨린다. 또한 thinking 토큰이 수백~수천 개라
# CPU 환경에서 latency 도 폭증.
#
# 3중 방어:
#   ① 프롬프트 prefix /no_think    — qwen3 공식 디렉티브로 thinking 자체 차단
#   ② payload "think": False      — Ollama 0.5+ 옵션, 모델 단에서 차단
#   ③ 응답 후처리 _strip_thinking — 위 둘이 무시되어도 결과 정제 (안전망)
_NO_THINK_DIRECTIVE = "/no_think"
_THINK_BLOCK = re.compile(r"<think>.*?</think>\s*", re.DOTALL | re.IGNORECASE)


def _strip_thinking(text: str) -> str:
    """LLM 응답에서 <think>...</think> 블록 제거. 없으면 원문 그대로."""
    if not text or "<think>" not in text.lower():
        return text
    return _THINK_BLOCK.sub("", text).lstrip()


def _prepend_no_think(text: str) -> str:
    """이미 디렉티브가 있으면 중복 추가하지 않음."""
    if not text:
        return _NO_THINK_DIRECTIVE
    if text.lstrip().startswith(_NO_THINK_DIRECTIVE):
        return text
    return f"{_NO_THINK_DIRECTIVE}\n{text}"


class OllamaClient:
    """
    Governance LLM 클라이언트 (정책 평가, Judge, Self-Consistency 용).
    SafeAgent 내부 도구로만 사용 — 검사 대상이 아님.
    Sovereign AI 호출은 SovereignAIClient 를 사용할 것.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = settings.governance_llm_url.rstrip("/")
        self.model = settings.governance_llm_model
        self.temperature = settings.governance_llm_temperature

    async def generate(
        self,
        prompt: str,
        temperature: float | None = None,
    ) -> str:
        """
        단일 프롬프트 방식 — 기존 Feature 1/2/JudgeEngine 호환성 유지.
        temperature 명시 시 Self-Consistency Check 등에서 변형된 출력 유도 가능.
        """
        payload = {
            "model": self.model,
            "prompt": _prepend_no_think(prompt),  # 방어 ①
            "stream": False,
            "think": False,                        # 방어 ②
            "options": {
                "temperature": temperature if temperature is not None else self.temperature
            },
        }
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(f"{self.base_url}/api/generate", json=payload)
            response.raise_for_status()
            data = response.json()
        return _strip_thinking(data.get("response", ""))  # 방어 ③

    async def chat(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float | None = None,
    ) -> str:
        """
        system/user 역할 분리 방식 — Feature 3 전용.
        /api/chat 엔드포인트 사용으로 프롬프트 인젝션 경계를 명확히 구분.
        temperature 오버라이드 가능 (Step 2 형식 변환 시 0.0 고정).
        """
        messages = []
        if system_prompt:  # 빈 문자열이면 system 메시지 생략
            messages.append({"role": "system", "content": system_prompt})
        # 사용자 메시지 앞에 /no_think 디렉티브 (방어 ①)
        messages.append({"role": "user", "content": _prepend_no_think(user_message)})

        payload = {
            "model": self.model,
            "stream": False,
            "think": False,  # 방어 ②
            "options": {
                "temperature": temperature if temperature is not None else self.temperature
            },
            "messages": messages,
        }
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(f"{self.base_url}/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()
        return _strip_thinking(data.get("message", {}).get("content", ""))  # 방어 ③
