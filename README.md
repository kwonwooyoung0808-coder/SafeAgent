# SafeAgent_Manager

회사 자체 AI (Sovereign AI) 의 입출력을 정책 기반으로 검사하고 위반 시 차단/경고/안전 대체 응답을 제공하는 **AI 거버넌스 게이트웨이** 입니다.

PRD 18.x 기준 자체 호스팅 (B2B) 배포를 가정하며, 데이터 주권 (사내망 외 데이터 유출 차단) 을 핵심 가치로 합니다.

---

## 핵심 기능

| Feature | 설명 | 라우터 |
|---------|------|-------|
| **F1 Input Guard** | 사용자 질의 위험 검사 (룰 기반, P95 ≤ 3s) | `POST /v1/input-guard/check` |
| **F2 Response Guard** | AI 응답 정책 준수 검증 (LLM Judge + Self-Consistency 옵션) | `POST /v1/response-guard/validate` |
| **F3 Policy Compiler** | `.docx` → YAML 정책 변환 + 버전 관리 | `POST /v1/policy-compiler/compile` |
| **Proxy Chat** | F1 → Sovereign AI → F2 자동 연결 (편의) | `POST /v1/proxy/chat` |

### 추가 기능 (Phase 1-3)

| 기능 | 위치 |
|------|------|
| Safe Response Generator (PRD §8) — 차단 시 안전 대체 응답 | `services/safe_response_generator.py` |
| Policy Violation Reporter (PRD §7) — 위반 자동 리포트 | `routers/violation_reports.py` |
| trace_id 체인 (PRD §6) — F1/F2/audit/violation 추적 | `core/dependencies.py:get_trace_id` |
| PII 마스킹 (PRD §6) — audit log 에 마스킹 사본 보존 | `utils/masker.py` |
| Policy Groups — 다대다 매핑 (부서/팀 단위) | `routers/policy_groups.py` |
| Policy Versions — 정책 버전 관리 + 롤백 | `routers/policy_versions.py` |
| 정책 메모리 캐시 — 핫패스 디스크 I/O 제거 | `utils/policy_cache.py` |
| 데이터 주권 가드 — 클라우드 LLM 자동 차단 (NIST SC-7(5)) | `services/sovereign_ai_client.py` |
| 운영 모니터링 — `/health/cache`, `/health/system`, `/health/llm` | `routers/health.py` |

---

## 빠른 시작

### 1. 사전 준비

- Python 3.10+
- PostgreSQL 18 (port 5433 권장)
- [Ollama](https://ollama.com/) + 모델 다운로드
  ```cmd
  ollama pull qwen2.5:7b
  ollama pull llama3.2:3b
  ```

### 2. 패키지 설치

```cmd
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 3. 환경변수 (`.env` 생성)

`.env.example` 을 복사 후 수정:

```env
APP_NAME=SafeAgent_Manager
DATABASE_URL=postgresql://postgres:YOUR_PW@localhost:5433/safeagent
POLICY_DIR=src/policies
PROMPT_DIR=src/prompts
WORKFLOW_NAME=governance_workflow

SYSTEM_INPUT_POLICY_ID=CONTENT_001
ENABLE_SELF_CONSISTENCY=false

# Governance LLM (F2 Judge)
GOVERNANCE_LLM_URL=http://localhost:11434
GOVERNANCE_LLM_MODEL=qwen2.5:7b
GOVERNANCE_LLM_TEMPERATURE=0.1

# Sovereign AI (검사 대상 회사 AI — 데이터 주권 가드 적용)
SOVEREIGN_AI_URL=http://localhost:11434
SOVEREIGN_AI_MODEL=qwen2.5:7b
SOVEREIGN_AI_TEMPERATURE=0.7
SOVEREIGN_ALLOWED_HOSTS=localhost,host.docker.internal,ollama
```

### 4. DB 생성 + 마이그레이션

```sql
-- psql 또는 DBeaver 에서
CREATE DATABASE safeagent;
```

```cmd
.venv\Scripts\python.exe -m scripts.run_migrations
```

상세 절차: [migrations/README.md](migrations/README.md)

### 5. 서버 실행

```cmd
.venv\Scripts\python.exe -m uvicorn src.main:app --port 8000 --reload
```

Swagger UI: http://localhost:8000/docs

---

## 환경변수 전체 가이드

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `DATABASE_URL` | `postgresql://...:5432/safeagent` | PostgreSQL 연결 |
| `POLICY_DIR` | `src/policies` | YAML 정책 폴더 |
| `PROMPT_DIR` | `src/prompts` | LLM 프롬프트 폴더 |
| `SYSTEM_INPUT_POLICY_ID` | `CONTENT_001` | F1 고정 시스템 정책 |
| `ENABLE_SELF_CONSISTENCY` | `false` | F2 Self-Consistency Check (true 시 LLM 2회 호출) |
| `GOVERNANCE_LLM_URL` | `localhost:11434` | F2 Judge LLM URL |
| `GOVERNANCE_LLM_MODEL` | `qwen2.5:7b` | F2 Judge 모델 |
| `SOVEREIGN_AI_URL` | `localhost:11434` | 검사 대상 회사 AI URL ⚠️ 주권 가드 적용 |
| `SOVEREIGN_AI_MODEL` | `qwen2.5:7b` | 회사 AI 모델 |
| `SOVEREIGN_ALLOWED_HOSTS` | `localhost,host.docker.internal,ollama` | 허용 호스트 (콤마 구분) |
| `SAFE_RESPONSE_LLM_*` | governance LLM 동일 | Safe Response Generator (현재 템플릿 기반, env 설정만 등록) |

### 데이터 주권 가드 (NIST SP 800-53 SC-7(5))

`SOVEREIGN_AI_URL` 은 다음 조건을 충족해야 시작됩니다:

1. `SOVEREIGN_ALLOWED_HOSTS` 에 명시 등록된 호스트, 또는
2. RFC 1918 사내 IP 대역 (`10/8`, `172.16/12`, `192.168/16`, `127/8`)

클라우드 LLM (`api.openai.com`, `api.anthropic.com` 등) 은 자동 차단. 운영자 실수 방지 + 신규 클라우드 자동 거부.

상세 설계: [docs/sovereignty_guard.md](docs/sovereignty_guard.md) (필요 시 작성)

---

## 모델 권장 (CPU 환경)

| 환경 | Governance LLM | Sovereign AI | 비고 |
|------|---------------|------------|------|
| **권장 (검증됨)** | `qwen2.5:7b` | `qwen2.5:7b` | 메모리 14GB, 안정 |
| 한국어 품질 우선 | `qwen2.5:7b` | `qwen3:8b` | swap 발생 가능 |
| 메모리 빡빡 (16GB) | 단일 모델 통일 권장 | 동일 | swap 진입 방지 |

`qwen3` 계열의 thinking 모드는 자동 차단됨 (`/no_think` + `think:false` + 응답 후처리).

---

## 주요 API

전체 목록은 Swagger UI 참조. 핵심 그룹만 발췌:

### F1/F2/F3 Pipeline
- `POST /v1/input-guard/check` — 질의 위험 검사
- `POST /v1/response-guard/validate` — 응답 정책 검증
- `POST /v1/policy-compiler/compile` — 정책 문서 변환
- `POST /v1/proxy/chat` — F1 → Sovereign AI → F2 자동 연결

### Audit / Reports
- `GET /v1/audit/query/{audit_id}` — F1 감사 로그 (trace_id, masked_query 포함)
- `GET /v1/audit/response/{audit_id}` — F2 감사 로그
- `GET /v1/violation-reports` — 차단/거부 자동 리포트 목록
- `PUT /v1/violation-reports/{id}/status` — 리포트 상태 변경

### Agent / Policy 관리
- `GET /api/agents` — 등록 에이전트 목록
- `POST /api/agents` — 에이전트 등록
- `GET /v1/policy-groups` — 정책 그룹 목록
- `POST /v1/policy-compiler/{policy_id}/versions` — 정책 새 버전
- `PUT /v1/policy-compiler/{policy_id}/versions/{version}/activate` — 버전 활성화 (롤백 포함)

### 운영 모니터링
- `GET /health` — 기본 헬스체크
- `GET /health/cache` — 정책 캐시 hit/miss 통계
- `GET /health/system` — DB + 엔터티 카운트
- `GET /health/llm` — Sovereign AI / Governance LLM 도달 가능성 (추론 호출 없음)

### trace_id 체인 추적

모든 응답에 `trace_id` 자동 발급. 클라이언트가 `X-Trace-Id` 헤더로 직접 지정 가능. 한 사용자 요청의 F1/F2 audit + violation_report 가 동일 trace_id 로 연결됨.

```cmd
curl -H "X-Trace-Id: my-request-001" -X POST ...
```

---

## 프로젝트 구조

```
src/
├─ main.py                       # FastAPI 앱 + lifespan
├─ core/                         # 설정, 의존성
│  ├─ config.py                  # Settings (env 파싱)
│  └─ dependencies.py            # get_db, get_trace_id
├─ database/
│  ├─ connection.py              # SessionLocal, init_db
│  └─ models.py                  # SQLAlchemy 모델
├─ engines/
│  ├─ judge_engine.py            # F2 Judge LLM 평가 (lru_cache 프롬프트)
│  └─ policy_engine.py           # F2 룰 평가
├─ policies/                     # YAML 정책 파일
├─ prompts/                      # LLM 프롬프트 템플릿
├─ routers/                      # FastAPI 라우터
│  ├─ input_guard.py             # F1 (PRD 명명규칙)
│  ├─ response_guard.py          # F2
│  ├─ policy_compiler.py         # F3
│  ├─ proxy.py                   # F1+F2 편의
│  ├─ agents.py                  # Agent CRUD + Policy Group 매핑
│  ├─ policy_groups.py           # Policy Group CRUD
│  ├─ policy_versions.py         # 버전 관리
│  ├─ violation_reports.py       # 위반 리포트
│  ├─ audit.py                   # 감사 로그 조회
│  ├─ inquiry.py                 # 사용자 문의
│  └─ health.py                  # 운영 모니터링
├─ schemas/                      # Pydantic 스키마
├─ services/
│  ├─ ollama_client.py           # Governance LLM (thinking 차단)
│  ├─ sovereign_ai_client.py     # 검사 대상 AI (주권 가드)
│  ├─ safe_response_generator.py # 차단 시 안전 응답 (PRD §8)
│  └─ violation_reporter.py      # 위반 자동 기록
├─ utils/
│  ├─ masker.py                  # PII 마스킹
│  ├─ policy_cache.py            # 정책 메모리 캐시
│  ├─ policy_combiner.py         # 다중 정책 결합 (Stage A)
│  └─ agent_policies.py          # F2 정책 ID 해석 (그룹 멤버 포함)
└─ workflows/
   ├─ input_guard_workflow.py    # LangGraph F1 (룰 only)
   └─ response_guard_workflow.py # LangGraph F2 (룰 + LLM Judge)

migrations/                       # DB 마이그레이션 SQL
scripts/run_migrations.py         # 마이그레이션 헬퍼
tests/
├─ unit/                          # 단위 테스트
└─ integration/                   # 통합 테스트
```

---

## 테스트

```cmd
.venv\Scripts\python.exe -m pytest tests/ -v
```

현재 **176/176 통과**. 통합 테스트는 PostgreSQL `safeagent_test` DB 를 자동 사용 (운영 DB 와 격리).

테스트 DB 1회 준비:
```sql
CREATE DATABASE safeagent_test;
```

---

## 트러블슈팅

### Sovereign AI 호출 실패: ReadTimeout
- 모델이 너무 커서 CPU 추론 시 timeout. 더 작은 모델 (qwen2.5:7b → llama3.2:3b) 로 교체 또는 timeout 상향.

### F2 Judge 응답 파싱 실패
- 작은 모델 (3B) 은 JSON 형식 못 지킴. `qwen2.5:7b` 이상 권장.

### qwen3 모델 timeout
- thinking 모드가 토큰 폭증. 자동 차단 코드 포함되어 있으나 latency 영향 잔존. CPU 환경은 `qwen2.5:7b` 권장.

### `agent-test-001` 등록 안 됨 오류
- DB 마이그레이션 후 또는 fresh DB. `POST /api/agents` 로 재등록:
  ```
  POST /api/agents { "id": "agent-test-001", "name": "Test", "policy_id": "CONTENT_001", "status": "ACTIVE" }
  ```

### `Sovereign AI URL 거부` 시작 실패
- 데이터 주권 가드. `.env` 의 `SOVEREIGN_AI_URL` 이 허용 호스트인지 확인. 사내 도메인은 `SOVEREIGN_ALLOWED_HOSTS` 추가.

---

## 관련 문서

- [migrations/README.md](migrations/README.md) — DB 마이그레이션 절차
- [.env.example](.env.example) — 환경변수 전체 예시
- Swagger UI — http://localhost:8000/docs (실행 후)
