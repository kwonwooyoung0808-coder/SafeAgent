# SafeAgent_Manager

> SafeAgent Manager는 기업 내규 기반의 **AI 거버넌스 솔루션**입니다. **입력 보안·응답 검증·정책 자동화·감사 추적** 4개 레이어가 온프레미스 환경에서 완전히 자동화됩니다.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Tests](https://img.shields.io/badge/Tests-231%2F231%20passed-brightgreen)
![License](https://img.shields.io/badge/License-MIT-lightgrey)

---

## 목차

1. [소개](#1-소개)
2. [주요 화면](#2-주요-화면)
3. [데모 영상](#3-데모-영상)
4. [핵심 기능](#4-핵심-기능)
5. [기술 스택](#5-기술-스택)
6. [아키텍처 개요](#6-아키텍처-개요)
7. [설치 방법](#7-설치-방법)
8. [환경변수 전체 가이드](#8-환경변수-전체-가이드)
9. [주요 API](#9-주요-api)
10. [프로젝트 구조](#10-프로젝트-구조)
11. [모델 권장 (CPU 환경)](#11-모델-권장-cpu-환경)
12. [테스트](#12-테스트)
13. [트러블슈팅](#13-트러블슈팅)
14. [향후 로드맵](#14-향후-로드맵)
15. [관련 문서](#15-관련-문서)

---

## 1. 소개

2023년 삼성전자 ChatGPT 기밀 유출 사고 이후, 대기업의 70% 이상이 사내망 전용 AI(sLLM) 도입을 추진하고 있습니다. 퍼블릭 AI의 편의성을 유지하면서 데이터 유출 리스크를 차단하는 거버넌스 체계가 필요합니다.

SafeAgent_Manager는 회사 전용 AI(Sovereign AI)의 입출력을 정책 기반으로 검사하고, 위반 시 즉시 차단·대체 응답을 제공하는 온프레미스 AI 거버넌스 게이트웨이입니다.

### 설계 원칙

| 원칙 | 내용 |
|------|------|
| **Fail-Closed** | 시스템 오류 시 모든 위험 접근 즉각 차단 (기본 차단 정책) |
| **100% 온프레미스** | 외부 네트워크 연결 없이 로컬 환경에서만 처리 |
| **설명 가능한 통제** | 차단 시 위반 사유(Policy Violation Report)를 투명하게 제공 |

**대상 사용자:** AI 거버넌스 담당자, 보안팀, 사내 AI 운영자

---

## 2. 주요 화면

<table>
  <tr>
    <td align="center"><b>보안 모니터링 대시보드</b></td>
    <td align="center"><b>AI 보안 비서 — 정책 위반 차단</b></td>
  </tr>
  <tr>
    <td><img src="docs/images/screenshot_01.png" alt="보안 모니터링 대시보드"/></td>
    <td><img src="docs/images/screenshot_02.png" alt="AI 보안 비서 정책 위반 차단"/></td>
  </tr>
  <tr>
    <td>실시간 보안 이벤트 현황, 감사 로그 집계, 시스템 무결성 점수를 한 화면에서 확인합니다.</td>
    <td>사내 정책상 금지된 질의를 입력하면 <code>ACCESS DENIED BY POLICY</code> 응답과 함께 안전 대체 메시지를 반환합니다.</td>
  </tr>
</table>

---

## 3. 데모 영상

<table>
  <tr>
    <td align="center">
      <a href="https://www.youtube.com/watch?v=QCunzYC9JdA" target="_blank">
        <img src="https://img.youtube.com/vi/QCunzYC9JdA/maxresdefault.jpg" alt="데모 영상 1" width="100%"/>
      </a>
    </td>
    <td align="center">
      <a href="https://www.youtube.com/watch?v=in9kr76a6ZI" target="_blank">
        <img src="https://img.youtube.com/vi/in9kr76a6ZI/maxresdefault.jpg" alt="데모 영상 2" width="100%"/>
      </a>
    </td>
  </tr>
</table>

---

## 4. 핵심 기능

| 기능명 | 설명 | 엔드포인트 |
|---------|------|-----------|
| **F1 Input Guard** | 사용자 질의 위험 검사 — LLM 미사용, 결정론적 룰 기반 (P95 ≤ 3s) | `POST /v1/input-guard/check` |
| **F2 Response Guard** | AI 응답 정책 준수 검증 (LLM Judge + Self-Consistency 옵션) | `POST /v1/response-guard/validate` |
| **F3 Policy Compiler** | `.docx` → YAML 정책 변환 + 버전 관리 | `POST /v1/policy-compiler/compile` |
| **Proxy Chat** | F1 → Sovereign AI → F2 자동 연결 (편의) | `POST /v1/proxy/chat` |

### 거버넌스 부가 기능

| 기능 | 위치 |
|------|------|
| Safe Response Generator — 차단 시 안전 대체 응답 | `services/safe_response_generator.py` |
| Policy Violation Reporter — 위반 자동 리포트 | `routers/violation_reports.py` |
| trace_id 체인 — F1/F2/audit/violation 전 구간 추적 | `core/dependencies.py` |
| PII 마스킹 — audit log 에 마스킹 사본 보존 | `utils/masker.py` |
| Policy Groups — 다대다 매핑 (부서/팀 단위) | `routers/policy_groups.py` |
| Policy Versions — 정책 버전 관리 + 롤백 | `routers/policy_versions.py` |
| 정책 메모리 캐시 — 핫패스 디스크 I/O 제거 | `utils/policy_cache.py` |
| 데이터 주권 가드 — 클라우드 LLM 자동 차단 (NIST SC-7(5)) | `services/sovereign_ai_client.py` |
| 운영 모니터링 — `/health/cache`, `/health/system`, `/health/llm` | `routers/health.py` |

---

## 5. 기술 스택

**Backend**  
![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Pydantic](https://img.shields.io/badge/Pydantic-E92063?style=for-the-badge&logo=pydantic&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-D71F00?style=for-the-badge&logo=sqlalchemy&logoColor=white)

**Orchestration**  
![LangGraph](https://img.shields.io/badge/LangGraph-1C3C3C?style=for-the-badge&logo=langchain&logoColor=white)

**Database**  
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)

**LLM Runtime**  
![Ollama](https://img.shields.io/badge/Ollama-000000?style=for-the-badge&logo=ollama&logoColor=white)

**Frontend**  
![React](https://img.shields.io/badge/React-61DAFB?style=for-the-badge&logo=react&logoColor=black)
![Vite](https://img.shields.io/badge/Vite-646CFF?style=for-the-badge&logo=vite&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?style=for-the-badge&logo=typescript&logoColor=white)
![Tailwind CSS](https://img.shields.io/badge/TailwindCSS-06B6D4?style=for-the-badge&logo=tailwindcss&logoColor=white)

**API Gateway**  
![Spring Boot](https://img.shields.io/badge/Spring_Boot-6DB33F?style=for-the-badge&logo=springboot&logoColor=white)

---

## 6. 아키텍처 개요

SafeAgent Manager는 4계층으로 구성됩니다.    
각 계층은 독립 배포·교체가 가능하며, 전 구간이 온프레미스 안에서 완결됩니다.

```
[ Layer 1: Client & Gateway ]  Spring Boot — JWT 인증, Rate Limiting
           │
           ▼
[ Layer 2: FastAPI Services ]  Input Guard / Response Guard / Policy Compiler
           │
           ▼
[ Layer 3: Orchestration    ]  LangGraph — 에이전트 파이프라인, Violation Reporter
           │
           ▼
[ Layer 4: Data & LLM       ]  Ollama (로컬) + PostgreSQL — 외부 네트워크 차단
```

### 요청 처리 흐름

사용자 요청은 F1 → Sovereign AI → F2 순서를 거칩니다.    
어느 단계에서든 위반이 감지되면 즉시 차단하고 안전 대체 응답을 반환합니다.

```
사용자 질의
    │
    ▼
┌──────────────────────────────────┐
│  F1 Input Guard                  │  결정론적 룰 기반 (LLM 미사용)
│  POST /v1/input-guard/check      │  (기밀·금지어·PII·프롬프트 인젝션 감지)
└────────┬─────────────┬───────────┘
         │ PASS        │ BLOCK
         ▼             ▼
         │        안전 대체 응답 + Violation Report
┌──────────────────────────────────┐
│  Sovereign AI                    │  사내 전용 LLM (Ollama 로컬)
│  (온프레미스 격리)                │  클라우드 LLM 자동 차단
└────────┬─────────────────────────┘
         │ AI 응답 생성
         ▼
┌──────────────────────────────────┐
│  F2 Response Guard               │  LLM Judge 정책 검증
│  POST /v1/response-guard/validate│  (환각·기밀·정책 위반 탐지)
└────────┬─────────────┬───────────┘
         │ PASS        │ BLOCK
         ▼             ▼
    최종 응답 반환  안전 대체 응답 + Violation Report
```

### trace_id 체인 추적

모든 단계에서 `trace_id`가 자동 발급되어 F1 audit · F2 audit · violation report가 단일 요청으로 연결됩니다. 클라이언트가 `X-Trace-Id` 헤더로 직접 지정할 수도 있습니다.

---

## 7. 설치 방법

### 1. 사전 준비

- Python 3.10+
- PostgreSQL 18 (port 5433 권장)
- [Ollama](https://ollama.com/) + 모델 다운로드 (모델 선택 기준: [11. 모델 권장](#11-모델-권장-cpu-환경))
  ```cmd
  ollama pull qwen2.5:7b
  ```

### 2. 패키지 설치

```cmd
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 3. 환경변수 설정

`.env.example`을 복사해 `.env`를 생성한 뒤, [7. 환경변수 전체 가이드](#7-환경변수-전체-가이드)를 참고하여 값을 수정합니다.

```cmd
copy .env.example .env
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

## 8. 환경변수 전체 가이드

`.env.example`을 복사 후 아래 표를 참고해 수정합니다:

```env
APP_NAME=SafeAgent_Manager
DATABASE_URL=postgresql://postgres:YOUR_PW@localhost:5433/safeagent
POLICY_DIR=src/policies
PROMPT_DIR=src/prompts
WORKFLOW_NAME=governance_workflow

SYSTEM_INPUT_POLICY_ID=CONTENT_001
ENABLE_SELF_CONSISTENCY=false

# Governance LLM (F2 Judge + F3 Policy Compiler)
GOVERNANCE_LLM_URL=http://localhost:11434
GOVERNANCE_LLM_MODEL=qwen2.5:7b
GOVERNANCE_LLM_TEMPERATURE=0.1

# Sovereign AI (검사 대상 회사 AI — 데이터 주권 가드 적용)
SOVEREIGN_AI_URL=http://localhost:11434
SOVEREIGN_AI_MODEL=qwen2.5:7b
SOVEREIGN_AI_TEMPERATURE=0.7
SOVEREIGN_ALLOWED_HOSTS=localhost,host.docker.internal,ollama
```

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `DATABASE_URL` | `postgresql://...:5432/safeagent` | PostgreSQL 연결 |
| `POLICY_DIR` | `src/policies` | YAML 정책 폴더 |
| `PROMPT_DIR` | `src/prompts` | LLM 프롬프트 폴더 |
| `SYSTEM_INPUT_POLICY_ID` | `CONTENT_001` | F1 고정 시스템 정책 |
| `ENABLE_SELF_CONSISTENCY` | `false` | F2 Self-Consistency Check (true 시 LLM 2회 호출) |
| `GOVERNANCE_LLM_URL` | `localhost:11434` | F2 Judge + F3 Compiler LLM URL |
| `GOVERNANCE_LLM_MODEL` | `qwen2.5:7b` | F2/F3 전용 모델 (고정밀 추론) |
| `SOVEREIGN_AI_URL` | `localhost:11434` | 검사 대상 회사 AI URL ⚠️ 주권 가드 적용 |
| `SOVEREIGN_AI_MODEL` | `qwen2.5:7b` | 회사 AI 모델 |
| `SOVEREIGN_ALLOWED_HOSTS` | `localhost,host.docker.internal,ollama` | 허용 호스트 (콤마 구분) |
| `SAFE_RESPONSE_LLM_*` | governance LLM 동일 | Safe Response Generator (현재 템플릿 기반) |

### 데이터 주권 가드 (NIST SP 800-53 SC-7(5))

`SOVEREIGN_AI_URL` 은 다음 조건을 충족해야 서버가 시작됩니다:

1. `SOVEREIGN_ALLOWED_HOSTS` 에 명시 등록된 호스트, 또는
2. RFC 1918 사내 IP 대역 (`10/8`, `172.16/12`, `192.168/16`, `127/8`)

클라우드 LLM (`api.openai.com`, `api.anthropic.com` 등)은 자동 차단됩니다. 운영자 실수 방지 및 신규 클라우드 엔드포인트 자동 거부.

상세 설계: [docs/sovereignty_guard.md](docs/sovereignty_guard.md)

---

## 9. 주요 API

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

---

## 10. 프로젝트 구조

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
│  ├─ input_guard.py             # F1
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
│  ├─ safe_response_generator.py # 차단 시 안전 응답
│  └─ violation_reporter.py      # 위반 자동 기록
├─ utils/
│  ├─ masker.py                  # PII 마스킹
│  ├─ policy_cache.py            # 정책 메모리 캐시
│  ├─ policy_combiner.py         # 다중 정책 결합
│  └─ agent_policies.py          # F2 정책 ID 해석 (그룹 멤버 포함)
└─ workflows/
   ├─ input_guard_workflow.py    # LangGraph F1 (룰 only)
   └─ response_guard_workflow.py # LangGraph F2 (룰 + LLM Judge)

migrations/                       # DB 마이그레이션 SQL
scripts/run_migrations.py         # 마이그레이션 헬퍼
tests/
├─ unit/                          # 단위 테스트 (77개)
└─ integration/                   # 통합 테스트 (154개)
```

---

## 11. 모델 권장 (CPU 환경)

각 기능별로 역할에 최적화된 모델을 분리해서 사용합니다:

| 역할 | 권장 모델 | 특징 |
|------|-----------|------|
| **F1 Input Guard** | — (LLM 미사용) | 결정론적 룰 기반, P95 ≤ 3s |
| **Sovereign AI** (회사 AI) | `qwen2.5:7b` | 안정적 한국어 추론, 메모리 7GB |
| **F2 Response Guard + F3 Policy Compiler** | `qwen2.5:7b` | 고정밀 추론, 내규 문서 이해 |

### 환경별 조합 권장

| 환경 | Governance LLM (F2/F3) | Sovereign AI | 비고 |
|------|------------------------|--------------|------|
| **권장 (검증됨)** | `qwen2.5:7b` | `qwen2.5:7b` | 총 메모리 14GB, 안정 |
| 한국어 품질 우선 | `qwen2.5:7b` | `qwen3:8b` | swap 발생 가능 |
| 메모리 빡빡 (16GB) | 단일 모델 통일 권장 | 동일 | swap 진입 방지 |

`qwen3` 계열의 thinking 모드는 자동 차단됨 (`/no_think` + `think:false` + 응답 후처리).

---

## 12. 테스트

```cmd
.venv\Scripts\python.exe -m pytest tests/ -v
```

현재 **231/231 통과** (Unit 77개, Integration 154개). 통합 테스트는 PostgreSQL `safeagent_test` DB를 자동 사용 (운영 DB와 격리).

### 보안 표준 검증 항목

| 표준 | 검증 내용 | 상태 |
|------|-----------|------|
| NIST SP 800-53 SC-7(5) | 데이터 주권 URL 검증 16개 | PASS |
| CVE-2022-29217 | JWT 알고리즘 혼동 공격 차단 | PASS |
| OWASP API2:2023 | 사용자 enumeration 방지 | PASS |
| ISMS-P 2.5/2.11 | 감사 로그 마커 검증 | PASS |
| OAuth 2.0 BCP | Refresh 토큰 최소 권한 원칙 | PASS |

테스트 DB 1회 준비:
```sql
CREATE DATABASE safeagent_test;
```

---

## 13. 트러블슈팅

### Sovereign AI 호출 실패: ReadTimeout
모델이 너무 커서 CPU 추론 시 timeout. 더 작은 모델 또는 timeout 상향.

### F2 Judge 응답 파싱 실패
작은 모델 (3B) 은 JSON 형식 못 지킴. `qwen2.5:7b` 이상 권장.

### qwen3 모델 timeout
thinking 모드가 토큰 폭증. 자동 차단 코드 포함되어 있으나 latency 영향 잔존. CPU 환경은 `qwen2.5:7b` 권장.

### `agent-test-001` 등록 안 됨 오류
DB 마이그레이션 후 또는 fresh DB. `POST /api/agents` 로 재등록:
```
POST /api/agents { "id": "agent-test-001", "name": "Test", "policy_id": "CONTENT_001", "status": "ACTIVE" }
```

### `Sovereign AI URL 거부` 시작 실패
데이터 주권 가드. `.env` 의 `SOVEREIGN_AI_URL` 이 허용 호스트인지 확인. 사내 도메인은 `SOVEREIGN_ALLOWED_HOSTS` 추가.

### Docker 이미지 Pull 실패 (ghcr.io denied)
레지스트리 인증 없이 `docker compose pull` 실행 시 발생. 오프라인 번들 방식으로 설치:
```cmd
docker load -i safeagent-api.tar
docker load -i safeagent-portal.tar
docker compose up -d
```

### Swagger는 정상인데 프론트 기능 미동작
서버 장애가 아닌 API 계약 불일치 문제. `/docs`, `/openapi.json`, `/health` 응답이 정상이면 서버는 정상. 프론트가 기대하는 request/response 스키마와 실제 백엔드 응답을 Swagger 기준으로 재검토.

### LangGraph 경고가 API 오류처럼 보이는 경우
`langgraph import` 시 내부 의존성 warning이 출력되지만 서버 실행 자체는 정상. `/health` 응답으로 실제 장애 여부를 구분.

---

## 14. 향후 로드맵

### 단기

| 항목 | 내용 |
|------|------|
| 관리자 UI 고도화 | 사내 인증(사원증) 연동, 역할별 권한 분리, 세션 가시화 |
| `.hwpx` 정책 지원 | 한국 기업 환경에 최적화된 문서 파이프라인 |

### 중기

| 항목 | 내용 |
|------|------|
| 멀티테넌트 아키텍처 | 기업별 데이터 격리, 부서 스코프 정책 자동 매핑 |
| SSO 연동 | LDAP / AD / OIDC 기반 인증 위임 |

### 장기

| 항목 | 내용 |
|------|------|
| 운영 안정화 | Docker 이미지 서명(cosign), Redis 분산 캐싱, Kubernetes 지원 |
| Forensic 감사 API | 특정 시점 정책 상태 재현 및 판정 결과 역추적 |

---

## 15. 관련 문서

- [migrations/README.md](migrations/README.md) — DB 마이그레이션 절차
- [.env.example](.env.example) — 환경변수 전체 예시
- Swagger UI — http://localhost:8000/docs (실행 후)
