# SafeAgent Manager 설치 및 반영 가이드

## 1. 설치 방식

현재 배포 번들은 오프라인 설치를 기본으로 합니다.

- 기본 방식: 오프라인 설치 (`docker load`)
- 필요 환경: Docker Engine, Docker Compose
- 별도 설치 불필요: PostgreSQL

PostgreSQL은 `docker-compose.release.yml` 안의 `postgres` 서비스가 같이 실행합니다.

## 2. 압축 해제 후 확인할 파일

압축을 해제한 폴더 안에 아래 파일이 있어야 합니다.

- `.env.release.example`
- `docker-compose.release.yml`
- `install.bat`
- `install.sh`
- `safeagent-api-v0.2.0.tar`
- `safeagent-dashboard-v0.2.0.tar`

`.tar` 파일이 없다면 오프라인 설치를 진행할 수 없습니다. 번들을 다시 받아주세요.

## 3. `.env` 파일 준비

`.env.release.example` 파일을 `.env`로 복사하거나 이름을 변경합니다.

### Windows

```powershell
Copy-Item .env.release.example .env
```

### Linux

```bash
cp .env.release.example .env
```

`.env` 파일은 일반 텍스트 파일이므로 VS Code 없이 메모장, Notepad++, nano 등으로 수정할 수 있습니다.

## 4. 반드시 확인하거나 수정할 항목

### 필수 수정

- `POSTGRES_PASSWORD`
  - PostgreSQL 컨테이너 비밀번호입니다.
- `DATABASE_URL`
  - 위 비밀번호와 같은 값으로 맞춰야 합니다.

예시:

```env
POSTGRES_PASSWORD=MyStrongPassword123
DATABASE_URL=postgresql://safeagent_app:MyStrongPassword123@postgres:5432/safeagent
```

### 환경에 따라 확인할 항목

- `GOVERNANCE_LLM_URL`
- `SOVEREIGN_AI_URL`
- `SAFE_RESPONSE_LLM_URL`

현재 예시는 `http://host.docker.internal:11434` 기준입니다. Ollama 또는 LLM 서버가 다른 주소에서 실행 중이면 실제 주소로 변경해야 합니다.

### 보통 그대로 사용 가능한 항목

- `SAFEAGENT_API_IMAGE=safeagent-api-local:v0.2.0`
- `SAFEAGENT_FRONTEND_IMAGE=safeagent-dashboard-local:v0.2.0`

오프라인 설치에서는 번들 안의 `.tar`를 `docker load`로 등록하므로 위 기본값을 그대로 쓰는 것이 맞습니다.

## 5. Windows 설치 방법

PowerShell 또는 명령 프롬프트에서 번들 폴더로 이동한 뒤:

```bat
install.bat
```

## 6. Linux 설치 방법

터미널에서 번들 폴더로 이동한 뒤:

```bash
chmod +x install.sh
./install.sh
```

## 7. 수동 설치 방법

스크립트 대신 직접 실행하려면 아래 순서로 진행합니다.

### 1) Docker 이미지 등록

```bash
docker load -i safeagent-api-v0.2.0.tar
docker load -i safeagent-dashboard-v0.2.0.tar
```

### 2) 컨테이너 실행

```bash
docker compose -f docker-compose.release.yml up -d
```

### 3) 마이그레이션 실행

```bash
docker compose -f docker-compose.release.yml exec api python -m scripts.run_migrations
```

## 8. 정상 반영 확인

아래 주소로 접속해 정상 구동 여부를 확인합니다.

- 프론트엔드: `http://localhost:3000`
- API 상태: `http://localhost:8000/health`
- Swagger UI: `http://localhost:8000/docs`

`http://localhost:5432` 는 PostgreSQL 포트이므로 브라우저로 열어도 정상 페이지가 나오지 않습니다.

## 9. 자주 헷갈리는 점

- 사용자는 VS Code가 없어도 설치할 수 있습니다.
- 사용자는 PostgreSQL을 따로 설치할 필요가 없습니다.
- `5432` 포트는 웹페이지가 아니라 DB 포트입니다.
- `8000` 루트 주소에서 `{"detail":"Not Found"}` 가 보여도 API가 죽었다는 뜻은 아닙니다. `8000/docs` 또는 `8000/health` 로 확인하세요.

## 10. 롤백 개념

롤백이 필요하면 이전 버전의 이미지 `.tar` 와 compose 설정을 보관한 뒤, 해당 이미지로 다시 `docker load` 해서 재배포하는 방식으로 진행합니다.
