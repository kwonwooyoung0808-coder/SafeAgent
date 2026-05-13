import os
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel
from dotenv import load_dotenv


load_dotenv()


# ──────────────────────────────────────────────────────────────
# 두 종류의 LLM 분리:
# 1) Governance LLM — 정책 평가/Judge 용도. SafeAgent 내부 도구.
# 2) Sovereign AI   — 검사 대상 회사 AI. 데모에서는 같은 Ollama 공유,
#                     운영 시 회사별 LLM URL 로 교체 (Agent 단위 매핑은 향후).
#
# 하위 호환: OLLAMA_* 환경변수가 있으면 두 LLM 모두 거기서 읽어옴.
# ──────────────────────────────────────────────────────────────
class Settings(BaseModel):
    app_name: str = os.getenv("APP_NAME", "SafeAgent_Manager")
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql://safeagent_app:safeagent_password@localhost:5432/safeagent",
    )
    policy_dir: str = os.getenv("POLICY_DIR", "src/policies")
    prompt_dir: str = os.getenv("PROMPT_DIR", "src/prompts")
    workflow_name: str = os.getenv("WORKFLOW_NAME", "governance_workflow")
    app_version: str = os.getenv("APP_VERSION", "0.1.0")
    update_channel: str = os.getenv("UPDATE_CHANNEL", "stable")
    update_manifest_path: str = os.getenv(
        "UPDATE_MANIFEST_PATH",
        str(Path("frontend") / "downloads" / "safeagent-release-manifest.json"),
    )
    update_bundle_path: str = os.getenv(
        "UPDATE_BUNDLE_PATH",
        str(Path("frontend") / "downloads" / "safeagent-deployment-bundle.zip"),
    )
    frontend_origin: str = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")
    app_timezone: str = os.getenv("APP_TIMEZONE", "Asia/Seoul")

    # ── 정책 분리 전략 (Stage A) ──
    # F1 (질의 검사) 는 모든 사용자에게 동일한 보편 안전 정책만 적용
    # F2 (응답 검증) 는 시스템 정책 + agent 의 부서별 정책을 결합
    system_input_policy_id: str = os.getenv("SYSTEM_INPUT_POLICY_ID", "CONTENT_001")
    default_company_policy_group_id: str = os.getenv(
        "DEFAULT_COMPANY_POLICY_GROUP_ID", "GLOBAL_COMPANY_RULES"
    )

    # ── F2 Self-Consistency Check (PRD §5.2.2) ──
    # True  : Judge LLM 을 temp=0.0 / temp=0.7 로 2회 병렬 호출 후 verdict 비교 (정확도 ↑, latency ↑)
    # False : 단일 호출만 (CPU 환경 권장 — 8B 모델 Self-Consistency 는 timeout 위험)
    enable_self_consistency: bool = os.getenv("ENABLE_SELF_CONSISTENCY", "false").lower() == "true"

    # ── Governance LLM (정책 평가/Judge 용 내부 도구) ──
    governance_llm_url: str = os.getenv(
        "GOVERNANCE_LLM_URL", os.getenv("OLLAMA_URL", "http://localhost:11434")
    )
    governance_llm_model: str = os.getenv(
        "GOVERNANCE_LLM_MODEL", os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
    )
    governance_llm_temperature: float = float(
        os.getenv("GOVERNANCE_LLM_TEMPERATURE", os.getenv("OLLAMA_TEMPERATURE", "0.1"))
    )

    # ── Policy Compiler runtime guards ──
    # 한국식 조문 문서는 구조화 draft를 우선 사용하고, 비조문 대형 문서만 제한된 LLM 청킹 처리.
    policy_compiler_timeout_seconds: int = int(os.getenv("POLICY_COMPILER_TIMEOUT_SECONDS", "300"))
    policy_compiler_max_llm_chunks: int = int(os.getenv("POLICY_COMPILER_MAX_LLM_CHUNKS", "4"))

    # ── Sovereign AI (검사 대상 회사 AI) ──
    sovereign_ai_url: str = os.getenv(
        "SOVEREIGN_AI_URL", os.getenv("OLLAMA_URL", "http://localhost:11434")
    )
    sovereign_ai_model: str = os.getenv(
        "SOVEREIGN_AI_MODEL", os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
    )
    sovereign_ai_temperature: float = float(
        os.getenv("SOVEREIGN_AI_TEMPERATURE", "0.7")  # 응답 생성은 다양성 허용
    )

    # ── Safe Response Generator (PRD §8 — 차단/거부 시 대체 응답 생성) ──
    # 빠른 응답을 위해 가벼운 모델 권장. 미설정 시 governance LLM 재사용.
    safe_response_llm_url: str = os.getenv(
        "SAFE_RESPONSE_LLM_URL",
        os.getenv("GOVERNANCE_LLM_URL", os.getenv("OLLAMA_URL", "http://localhost:11434")),
    )
    safe_response_llm_model: str = os.getenv(
        "SAFE_RESPONSE_LLM_MODEL",
        os.getenv("GOVERNANCE_LLM_MODEL", os.getenv("OLLAMA_MODEL", "qwen2.5:7b")),
    )
    safe_response_llm_temperature: float = float(
        os.getenv("SAFE_RESPONSE_LLM_TEMPERATURE", "0.3")
    )

    # ── 환경 구분 ──
    # development | production. 운영 환경에서는 추가 보안 검증 활성화.
    app_env: str = os.getenv("APP_ENV", "development").lower()
    demo_auth_bypass: bool = os.getenv("DEMO_AUTH_BYPASS", "false").lower() == "true"

    # ── Phase 4: 인증/권한 ──
    # JWT_SECRET 은 운영 환경에서 반드시 32바이트 이상 랜덤 문자열로 교체 (RFC 7518 §3.2).
    jwt_secret: str = os.getenv(
        "JWT_SECRET", "dev-only-secret-change-me-in-production-32bytes-min"
    )
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    jwt_access_token_ttl_minutes: int = int(os.getenv("JWT_ACCESS_TOKEN_TTL_MINUTES", "60"))
    jwt_refresh_token_ttl_days: int = int(os.getenv("JWT_REFRESH_TOKEN_TTL_DAYS", "7"))
    bootstrap_admin_username: str = os.getenv("BOOTSTRAP_ADMIN_USERNAME", "admin")
    bootstrap_admin_password: str = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "changeme")


# ──────────────────────────────────────────────────────────────
# 시작 시 보안 검증 (fail-fast)
# RFC 7518 §3.2 / 운영 환경 약한 패스워드 차단
# ──────────────────────────────────────────────────────────────
_WEAK_BOOTSTRAP_PASSWORDS = {"changeme", "admin", "password", "1234", "", "test"}


def _validate_auth_settings(settings: "Settings") -> None:
    """JWT_SECRET 길이 + 운영 환경 약한 admin 비밀번호 차단."""
    if len(settings.jwt_secret.encode("utf-8")) < 32:
        raise ValueError(
            "JWT_SECRET 이 RFC 7518 §3.2 최소 요건(32바이트) 미달. "
            f"현재 {len(settings.jwt_secret.encode('utf-8'))}바이트. "
            "생성 예: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
        )
    if (
        settings.app_env == "production"
        and settings.bootstrap_admin_password.lower() in _WEAK_BOOTSTRAP_PASSWORDS
    ):
        raise ValueError(
            "운영 환경(APP_ENV=production)에서 BOOTSTRAP_ADMIN_PASSWORD 가 "
            "취약한 기본값입니다. 강력한 비밀번호로 교체하세요."
        )
    if settings.app_env == "production" and settings.demo_auth_bypass:
        raise ValueError(
            "DEMO_AUTH_BYPASS=true 는 production 환경에서 사용할 수 없습니다. "
            "운영에서는 JWT/API Key 인증을 반드시 활성화하세요."
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
