@echo off
setlocal

echo [SafeAgent] Starting offline deployment on Windows...

if not exist ".env" (
  if exist ".env.release.example" (
    copy ".env.release.example" ".env" >nul
    echo [SafeAgent] Created .env from .env.release.example.
    echo [SafeAgent] Please review DB password and LLM URLs before retrying.
    exit /b 1
  ) else (
    echo [SafeAgent] Missing .env.release.example file.
    exit /b 1
  )
)

if not exist "safeagent-api-v0.2.0.tar" (
  echo [SafeAgent] Missing safeagent-api-v0.2.0.tar.
  echo [SafeAgent] Please download the latest deployment bundle again.
  exit /b 1
)

if not exist "safeagent-dashboard-v0.2.0.tar" (
  echo [SafeAgent] Missing safeagent-dashboard-v0.2.0.tar.
  echo [SafeAgent] Please download the latest deployment bundle again.
  exit /b 1
)

echo [SafeAgent] Loading API image...
docker load -i safeagent-api-v0.2.0.tar
if errorlevel 1 exit /b 1

echo [SafeAgent] Loading portal image...
docker load -i safeagent-dashboard-v0.2.0.tar
if errorlevel 1 exit /b 1

echo [SafeAgent] Starting containers...
docker compose -f docker-compose.release.yml up -d
if errorlevel 1 (
  echo [SafeAgent] Failed to start containers.
  exit /b 1
)

echo [SafeAgent] Running database migrations...
docker compose -f docker-compose.release.yml exec api python -m scripts.run_migrations
if errorlevel 1 (
  echo [SafeAgent] Failed to run migrations.
  exit /b 1
)

echo [SafeAgent] Offline deployment completed successfully.
endlocal
