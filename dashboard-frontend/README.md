# SafeAgent Dashboard Frontend

이 프로젝트는 SafeAgent 거버넌스 시스템의 관리 대시보드 및 사용자 챗봇 인터페이스입니다.

## 🚀 주요 기능 (Main Features)

1.  **Role Selection Gateway**: 별도의 번거로운 절차 없이 관리자(Admin)와 사용자(Employee) 역할을 선택하여 진입할 수 있는 전문적인 관문 페이지를 제공합니다.
2.  **Silent Admin Login**: 관리자 포털 진입 시, 시스템이 자동으로 백엔드 기본 권한으로 인증을 수행하여 `401 Unauthorized` 에러 없이 즉시 데이터를 조회할 수 있도록 설계되었습니다.
3.  **AI Policy Compiler**: 사내 보안 규범(`.docx`)을 드래그-앤-드롭만으로 분석하여 AI 가드레일(`YAML`)로 자동 변환하고 즉시 시스템에 배포할 수 있는 기능을 제공합니다.
4.  **Security Audit & Trace**: 모든 AI 질의 이력을 추적하며, PII(개인정보) 마스킹 처리 전/후 데이터를 인스펙터 화면을 통해 상세히 비교할 수 있습니다.
5.  **Real-time Intelligence**: 대시보드에서 시스템 가동 상태, 보안 위반 실시간 분포, 에이전트 활동 통계를 시각화하여 보여줍니다.

## 🛠 기술 스택 (Tech Stack)

*   **Frontend**: Vite, React, TypeScript
*   **Styling**: Vanilla CSS (TailwindCSS 기반의 Modern Premium UI)
*   **Charts**: Recharts (보안 이벤트 및 통계 시각화)
*   **Icons**: Lucide React
*   **API Client**: Axios (Proxy 기반의 백엔드 통합)

## 📡 시스템 아키텍처 및 API 상세

프론트엔드는 다음 백엔드 설정을 통해 데이터를 연동합니다.

### 1. 운영 모니터링 (Health & Stats)
- `GET /health/system`: DB 연결 상태 및 등록된 에이전트/감사 로그 카운트 정보를 가져옵니다.
- `GET /health/llm`: 연동된 외부 LLM 및 로컬 Ollama 엔진의 가동 상태를 확인합니다.

### 2. 정책 컴파일 관리 (Policy Compiler)
- `GET /v1/policy-compiler`: 현재 등록된 모든 보안 정책의 목록과 활성 상태를 조회합니다. **(신규 추가)**
- `POST /v1/policy-compiler/compile`: `.docx` 문서를 업로드하여 AI 정책 파일로 변환을 요청합니다.
- `PUT /v1/policy-compiler/{id}/activate`: 분석된 정책을 실제 가드레일 엔진에 활성화(캐시 갱신 포함) 처리합니다.
- `GET /v1/policy-compiler/{id}/yaml`: 생성된 YAML 정책의 원본 명세를 조회합니다.

### 3. 보안 이벤트 관리 (Violations & Audit)
- `GET /v1/violation-reports`: 차단 또는 거부된 주요 보안 위반 사례를 칸반(Kanban) 큐 형태로 제공합니다.
- `GET /api/v1/audit-logs`: 모든 AI 호출 이력 및 마스킹 상세 데이터를 실시간 스트림 형태로 제공합니다.

## 📖 사내 정책 관리 가이드 (Usage Guide)

새로운 사내 보안 규정을 시스템에 적용하는 방법은 다음과 같습니다.

1.  **문서 준비**: 사내 보안 가이드라인이 담긴 `.docx` 파일을 준비합니다.
2.  **정책 업로드**: `Policy Compiler` 메뉴에서 정책 명칭을 입력하고 파일을 업로드합니다.
3.  **AI 분석 및 컴파일**: 'Start Compilation' 버튼을 누르면 시스템이 조문을 분석하여 가드레일 규칙을 생성합니다.
4.  **검토 및 미리보기**: 생성된 리스트에서 'Inspect YAML'을 눌러 실제 적용될 규칙들을 미리 확인합니다.
5.  **즉시 배포**: 'Activate System' 버튼을 클릭하면 즉시 해당 정책이 실시간 가드레일 엔진에 반영됩니다.

## 💻 실행 방법

```bash
# 의존성 설치
npm install

# 개발 서버 실행
npm run dev
```

## 🚀 실무 시스템 전환 가이드 (Production Transition)

현재 대시보드는 개발 및 데모 편의를 위해 **Silent Admin Login**과 **Auth Bypass** 기술이 적용되어 있습니다. 향후 정식 회원가입 및 로그인 시스템으로 전환할 때 다음 항목들을 순서대로 수정하십시오.

### 1. 백엔드 보안 강화 (`.env` 및 `src/core/config.py`)
- `.env` 파일의 `AUTH_ENABLED`를 `true`로 설정하십시오.
- `DEMO_AUTH_BYPASS` 설정이 있다면 반드시 `false`로 변경하거나 제거하십시오.
- `JWT_SECRET`을 유추 불가능한 32바이트 이상의 문자열로 교체하십시오.

### 2. 프론트엔드 인증 로직 교체 (`src/contexts/AuthContext.tsx`)
- `loginAsAdmin` 함수의 자동 ID/PW 입력을 제거하고, 실제 로그인 폼에서 전달받은 자격 증명을 `/v1/auth/login` 엔드포인트로 전송하도록 수정하십시오.
- 역할 선택(`RoleSelection.tsx`) 페이지를 정식 로그인/회원가입 디자인으로 교체하고 라우팅을 연결하십시오.

### 3. API 엔드포인트 권한 분리 (`src/main.py`)
- 현재 데모를 위해 `proxy.router`에 허용된 `_jwt_any` 의존성을 제거하고, 다시 `_machine` (API Key 전용)으로 제한하거나, 별도의 `Employee` 역할을 정의하여 엄격하게 분리하십시오.
- `app.include_router(proxy.router, dependencies=[Depends(require_role("employee"))])` 형태의 명확한 역할 정의가 필요합니다.

### 4. 에러 핸들링 복구 (`src/lib/api.ts`)
- 현재는 데모를 위해 401 에러 발생 시 리다이렉트를 막아두었습니다. 실무 환경에서는 토큰 만료 시 로그인 페이지로 강제 이동하도록 인터셉터 로직을 복구하십시오.

---
모든 데이터는 백엔드(`http://localhost:8000`)의 가동 상태에 따라 실시간으로 동기화됩니다.
