# SafeAgent Deployment Portal

이 포털은 Docker 없이도 별도 정적 사이트로 먼저 배포할 수 있습니다.

## 포함 파일

- `index.html`
- `styles.css`
- `app.js`
- `downloads/`

`app.js` 는 같은 사이트의 `./downloads/safeagent-release-manifest.json` 과
`./downloads/safeagent-deployment-bundle.zip` 을 직접 읽도록 구성되어 있습니다.
즉, 제품 백엔드가 없어도 포털만 독립 배포할 수 있습니다.

## 권장 배포 방식

### 1. 정적 웹서버에 업로드

다음 파일과 폴더를 그대로 웹 루트에 업로드합니다.

- `index.html`
- `styles.css`
- `app.js`
- `downloads/`

예시 주소:

- `https://download.safeagent.example/`

### 2. Nginx 사용

이미 포함된 `nginx.conf` 와 `Dockerfile` 을 사용하거나,
정적 파일만 기존 Nginx 문서 루트에 복사해도 됩니다.

### 3. IIS 또는 사내 웹서버 사용

동일하게 정적 파일 업로드만으로 배포할 수 있습니다.
별도 빌드 단계는 필요 없습니다.

## 배포 전 확인

1. `downloads/safeagent-release-manifest.json` 이 최신 버전 정보를 가리키는지 확인
2. `downloads/safeagent-deployment-bundle.zip` 이 최신 배포 번들인지 확인
3. 필요한 경우 `.tar` 이미지 파일들이 `downloads/` 아래 포함되어 있는지 확인

## 로컬 테스트

Python 이 설치되어 있다면 아래처럼 간단히 확인할 수 있습니다.

```powershell
cd frontend
python -m http.server 3000
```

브라우저:

- `http://127.0.0.1:3000`

## 정적 배포용 ZIP 생성

아래 스크립트를 실행하면 정적 배포용 포털 ZIP 이 생성됩니다.

```powershell
python -m scripts.build_frontend_portal_bundle
```

생성 결과:

- `frontend/downloads/safeagent-portal-static-site.zip`
