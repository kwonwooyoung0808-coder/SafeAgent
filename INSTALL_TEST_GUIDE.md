# SafeAgent 배포 번들 설치 테스트 가이드

## 목적
이 문서는 사용자가 배포 포털에서 받은 배포 번들 ZIP으로 실제 설치 테스트를 진행할 때 참고하는 가이드입니다.

## 사용자에게 필요한 환경
- Docker Desktop 또는 Docker Engine 설치
- `docker compose` 명령 사용 가능
- ZIP 압축 해제 가능
- `3000`, `8000`, `5432` 포트 사용 가능
- 폴더/파일 생성 권한

## 사용자에게 필요하지 않은 것
- Node.js
- Python 직접 설치
- VS Code

배포 번들 안에 설치 스크립트와 Docker 이미지 `.tar`가 들어 있으므로, Docker만 준비되어 있으면 설치 테스트를 진행할 수 있습니다.

## 다운로드 위치
배포 포털에서 아래 항목을 받습니다.

- `배포 번들 ZIP 받기`

이 파일 하나에 설치 테스트에 필요한 주요 파일이 포함되어 있습니다.

## ZIP 안에 들어 있어야 하는 파일
압축을 풀었을 때 아래 파일들이 있는지 확인합니다.

- `install.bat`
- `install.sh`
- `docker-compose.release.yml`
- `.env.release.example`
- `install-guide.md`
- `safeagent-api-v0.2.0.tar`
- `safeagent-portal-v0.2.0.tar`

## 설치 테스트 전 확인사항
같은 PC에서 기존 SafeAgent가 이미 실행 중이면 포트 충돌이 날 수 있습니다.

확인 포트:
- `3000`: 프론트
- `8000`: 백엔드 API
- `5432`: PostgreSQL

기존 컨테이너가 실행 중이면 먼저 중지합니다.

```powershell
docker compose down
```

## 설치 테스트 절차

### 1. 배포 포털 접속
- 브라우저에서 배포 포털에 접속합니다.
- 예: `http://localhost:3000`

### 2. 배포 번들 ZIP 다운로드
- `배포 번들 ZIP 받기` 버튼을 클릭합니다.

### 3. 새 폴더에 압축 해제
예:

```text
C:\safeagent-test\
```

### 4. `.env` 파일 준비
`.env.release.example`를 `.env`로 복사합니다.

Windows PowerShell 예시:

```powershell
Copy-Item .env.release.example .env
```

처음 테스트라면 기본값으로도 확인은 가능하지만, 운영 환경에서는 DB 비밀번호나 LLM 주소를 실제 환경에 맞게 수정해야 합니다.

### 5. Windows에서 설치 실행
압축 푼 폴더에서 실행:

```powershell
.\install.bat
```

### 6. Linux에서 설치 실행

```bash
chmod +x install.sh
./install.sh
```

## 설치 스크립트가 하는 일
설치 스크립트는 다음 순서로 동작합니다.

1. `.env` 파일이 없으면 `.env.release.example`를 복사
2. 같은 폴더에 `.tar` 이미지가 있으면 `docker load` 실행
3. `.tar`가 없으면 온라인 레지스트리에서 `docker compose pull`
4. `docker compose up -d`
5. `python -m scripts.run_migrations` 실행

## 설치 후 확인 방법

### 1. 컨테이너 확인

```powershell
docker ps
```

아래 서비스가 떠 있으면 정상입니다.
- API
- frontend
- postgres

### 2. 브라우저 확인
- 프론트: `http://localhost:3000`
- 백엔드 헬스체크: `http://localhost:8000/health`
- Swagger: `http://localhost:8000/docs`

### 3. 정상 설치 판단 기준
아래가 되면 기본 설치는 성공입니다.

- 포털 화면이 열림
- `/health` 응답이 옴
- Swagger 문서가 열림
- Docker 컨테이너가 정상 실행 중임

## 자주 생기는 문제

### 1. 포트 충돌
기존 컨테이너가 이미 `3000`, `8000`, `5432`를 쓰고 있을 수 있습니다.

### 2. Docker 미실행
Docker Desktop이 켜져 있지 않으면 설치가 실패합니다.

### 3. `.env` 값 불일치
DB 비밀번호, 내부 LLM 주소 등이 실제 환경과 다르면 실행 후 오류가 날 수 있습니다.

### 4. 마이그레이션 실패
API 컨테이너는 떴지만 DB 연결이나 권한 문제로 마이그레이션이 실패할 수 있습니다.

## 같은 PC 한 대로 테스트할 때 권장 순서

1. 기존 SafeAgent 컨테이너 중지
2. 배포 번들 ZIP 다운로드
3. 새 폴더에 압축 해제
4. `.env` 준비
5. `install.bat` 또는 `install.sh` 실행
6. `3000`, `8000` 접속 확인

## 참고
이 테스트는 "사용자가 번들을 받아 실제 설치 가능한지"를 확인하는 목적입니다.
다른 고객사 서버와 완전히 동일한 검증은 별도 PC, VM, 서버에서 추가로 진행하는 것이 가장 안전합니다.
