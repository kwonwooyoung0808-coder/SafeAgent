from __future__ import annotations

import ipaddress
import os
from urllib.parse import urlsplit

import httpx

from src.core.config import get_settings
from src.services.ollama_client import _prepend_no_think, _strip_thinking


# ──────────────────────────────────────────────────────────────────
# 데이터 주권 가드 — Allowlist (Default-Deny)
#
# 보안 원칙: NIST SP 800-53 Rev.5 SC-7(5) — Deny by Default / Allow by Exception
#   "필수적이고 승인된 연결만 허용한다. 명시되지 않은 모든 호스트는 차단."
# PRD §10.1: 사용자 데이터는 회사 인프라 밖으로 나가지 않는다.
#
# 출처:
#   NIST SP 800-53 Rev.5 SC-7(5)
#   RFC 1918 (사내 IP 대역)
#   Apple Support 101903 — .local mDNS 충돌 (TLD 자동 허용 미적용 사유)
#
# 허용 조건 (하나라도 충족하면 통과):
#   1. SOVEREIGN_ALLOWED_HOSTS 명시 등록
#   2. RFC 1918 사내 IP 대역 (10/8, 172.16/12, 192.168/16, 127/8)
# 그 외 모든 호스트 → 거부 (default-deny)
# ──────────────────────────────────────────────────────────────────

# 운영 마찰 최소화: 개발/Docker 환경 표준 패턴만 기본 허용
#   localhost              : 로컬 직접 실행
#   host.docker.internal   : Docker Desktop (Windows/Mac)
#   ollama                 : Docker Compose service 명 관례
_DEFAULT_ALLOWED_HOSTS = "localhost,host.docker.internal,ollama"


def _load_allowed_hostnames() -> frozenset[str]:
    """SOVEREIGN_ALLOWED_HOSTS 환경변수 파싱. 함수 호출 시점에 매번 읽어
    테스트의 monkeypatch.setenv 도 즉시 반영되도록 함."""
    raw = os.getenv("SOVEREIGN_ALLOWED_HOSTS", _DEFAULT_ALLOWED_HOSTS)
    return frozenset(h.strip().lower() for h in raw.split(",") if h.strip())


_ALLOWED_PRIVATE_NETWORKS: list[ipaddress.IPv4Network] = [
    ipaddress.ip_network("10.0.0.0/8"),      # RFC 1918 Class A
    ipaddress.ip_network("172.16.0.0/12"),   # RFC 1918 Class B
    ipaddress.ip_network("192.168.0.0/16"),  # RFC 1918 Class C
    ipaddress.ip_network("127.0.0.0/8"),     # Loopback (RFC 5735)
]
#  IPv6 (::1 등) 미지원 — 필요 시 별도 추가.
#  TLD 자동 허용 (.local, .internal 등) 미적용:
#    - 국내 중견~대기업은 공개 도메인 서브도메인 패턴 사용
#    - Apple .local 은 mDNS (RFC 6762) 예약, 사내 DNS 충돌 가능
#    - default-deny 원칙 약화 방지
#    → 사내 도메인은 SOVEREIGN_ALLOWED_HOSTS 에 명시 등록.


def _validate_sovereign_url(url: str) -> None:
    """SOVEREIGN_AI_URL 이 사내 허용 호스트인지 검증.

    허용 조건 미충족 시 ValueError. startup / __init__ 어느 시점에서나 사용 가능.
    """
    if not url or not url.strip():
        raise ValueError(
            " SOVEREIGN_AI_URL 이 비어 있습니다.\n"
            "설정 예: SOVEREIGN_AI_URL=http://ollama:11434\n"
            "     또는 SOVEREIGN_AI_URL=http://192.168.10.50:11434"
        )

    # urlsplit: 보안 결정 시 권장 (urlparse 보다 엄격, 입력 검증 안 하므로 추가 검증 필수)
    normalized = url if "://" in url else f"http://{url}"
    parsed = urlsplit(normalized)
    host = (parsed.hostname or "").lower().strip()

    if not host:
        raise ValueError(
            f" SOVEREIGN_AI_URL='{url}' 에서 호스트를 파싱할 수 없습니다.\n"
            "올바른 형식 예시:\n"
            "  http://ollama:11434\n"
            "  http://192.168.10.50:11434\n"
            "  http://ollama.internal.company.co.kr:11434"
        )

    allowed_hosts = _load_allowed_hostnames()

    # 검사 1: 명시적 허용 호스트
    if host in allowed_hosts:
        return  #  통과

    # 검사 2: RFC 1918 사내 IP 대역 — control flow 명확히 분리
    parsed_ip: ipaddress.IPv4Address | ipaddress.IPv6Address | None = None
    try:
        parsed_ip = ipaddress.ip_address(host)
    except ValueError:
        pass  # IP 형식 아님 → 도메인으로 진행

    if parsed_ip is not None:
        for network in _ALLOWED_PRIVATE_NETWORKS:
            if parsed_ip in network:
                return  #  사내 IP 통과
        raise ValueError(
            f" SOVEREIGN_AI_URL='{url}' 거부\n"
            f"   IP '{host}' 가 RFC 1918 사내 대역에 없습니다.\n\n"
            "허용 IP 대역 (RFC 1918):\n"
            + "\n".join(f"  - {n}" for n in _ALLOWED_PRIVATE_NETWORKS)
            + "\n\n"
            "공인 IP 는 데이터 주권 정책상 허용되지 않습니다.\n"
            "사내 IP 또는 SOVEREIGN_ALLOWED_HOSTS 에 등록된 도메인을 사용하세요."
        )

    # default-deny: 명시적 허용 조건 모두 불충족
    raise ValueError(
        f" SOVEREIGN_AI_URL='{url}' 거부\n"
        f"   호스트 '{host}' 가 허용 목록에 없습니다.\n\n"
        f"현재 허용 호스트:  {sorted(allowed_hosts)}\n"
        f"현재 허용 IP 대역: {[str(n) for n in _ALLOWED_PRIVATE_NETWORKS]}\n\n"
        "해결 방법:\n"
        "  SOVEREIGN_ALLOWED_HOSTS 환경변수에 호스트를 추가하세요.\n\n"
        "설정 예시:\n"
        "  # 사내 도메인 서브도메인 패턴 (국내 중견~대기업 표준)\n"
        "  SOVEREIGN_ALLOWED_HOSTS=ollama.internal.company.co.kr,localhost\n\n"
        "  # Docker Compose 단독 운영\n"
        "  SOVEREIGN_ALLOWED_HOSTS=ollama,localhost,host.docker.internal\n\n"
        "보안 정책: NIST SP 800-53 Rev.5 SC-7(5) — Deny by Default / Allow by Exception\n"
        "PRD §10.1: 사용자 데이터는 회사 인프라 밖으로 나갈 수 없습니다."
    )


# 한국어/영어 허용 + 그 외 외국어 차단 시스템 프롬프트.
# qwen2.5 계열은 중국어 학습 비중이 커 한국어 prompt 에 중국어가 leak 되는 경우가 있음.
# system role 로 명시적으로 강제 → leak 80-90% 차단.
_KOREAN_PERSONA_SYSTEM = (
    "당신은 한국 회사의 사내 AI 어시스턴트입니다. "
    "답변 언어는 한국어를 기본으로 하되, 필요 시 영어 사용을 허용합니다. "
    "중국어(중문), 일본어, 그 외 외국어 사용은 절대 금지합니다. "
    "코드/기술 용어는 영문 그대로 사용해도 좋으나, 본문 설명은 한국어로 작성하세요. "
    "답변은 간결하게 핵심만 작성하세요. 불필요한 반복이나 장황한 부연 설명은 피하고, "
    "예시는 1-2개로 제한합니다. 사용자가 추가 설명을 요청하면 그때 상세히 답변하세요."
)


class SovereignAIClient:
    """
    Sovereign AI 호출 클라이언트 — 검사 대상 회사 AI 에 응답을 요청.

    데모 환경에서는 Governance LLM 과 같은 Ollama 인스턴스를 공유하지만,
    환경변수 (SOVEREIGN_AI_*) 가 분리되어 있어 운영 시 회사 자체 LLM URL 로
    교체 가능. Agent 단위 매핑은 향후 AgentModel 에 컬럼으로 추가될 예정.

    PRD §10.1 데이터 주권 정책: 사내 자체 호스팅 LLM (Ollama 등) 만 호출.
    /api/chat 엔드포인트로 system/user 역할을 분리해 언어 강제 지시의
    우선순위를 높임 (qwen2.5 의 중국어 leak 방지).
    """

    def __init__(self) -> None:
        settings = get_settings()
        # 데이터 주권 가드 — 클라우드/공인 IP/미등록 호스트는 즉시 거부
        _validate_sovereign_url(settings.sovereign_ai_url)
        self.base_url = settings.sovereign_ai_url.rstrip("/")
        self.model = settings.sovereign_ai_model
        self.temperature = settings.sovereign_ai_temperature

    async def generate(
        self,
        query: str,
        context: str | None = None,
    ) -> str:
        """사원 질의 → 회사 AI 응답. 한국어/영어 강제 시스템 프롬프트 적용."""
        user_msg = f"질문: {query}"
        if context:
            user_msg = f"컨텍스트: {context}\n\n{user_msg}"

        # /api/chat — system role 로 언어 강제. /no_think 는 user 메시지에 prefix.
        # qwen3 등 thinking-mode 모델 회피 + qwen2.5 의 중국어 leak 차단을 동시 수행.
        payload = {
            "model": self.model,
            "stream": False,
            "think": False,
            "options": {"temperature": self.temperature},
            "messages": [
                {"role": "system", "content": _KOREAN_PERSONA_SYSTEM},
                {"role": "user", "content": _prepend_no_think(user_msg)},
            ],
        }
        async with httpx.AsyncClient(timeout=180.0) as client:
            # 디버깅을 위한 print 코드 추가 (사용자 요청)
            print(f"[DEBUG] Calling Sovereign AI: {self.base_url}/api/chat")
            print(f"[DEBUG] Payload: {payload}")
            
            response = await client.post(f"{self.base_url}/api/chat", json=payload)
            
            print(f"[DEBUG] Response Status: {response.status_code}")
            
            response.raise_for_status()
            data = response.json()
        return _strip_thinking(data.get("message", {}).get("content", ""))
