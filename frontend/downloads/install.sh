#!/usr/bin/env sh
set -eu

echo "[SafeAgent] Starting offline deployment on Linux..."

if [ ! -f ".env" ]; then
  if [ -f ".env.release.example" ]; then
    cp .env.release.example .env
    echo "[SafeAgent] Created .env from .env.release.example."
    echo "[SafeAgent] Please review DB password and LLM URLs before retrying."
    exit 1
  else
    echo "[SafeAgent] Missing .env.release.example file."
    exit 1
  fi
fi

if [ ! -f "safeagent-api-v0.2.0.tar" ]; then
  echo "[SafeAgent] Missing safeagent-api-v0.2.0.tar."
  echo "[SafeAgent] Please download the latest deployment bundle again."
  exit 1
fi

if [ ! -f "safeagent-dashboard-v0.2.0.tar" ]; then
  echo "[SafeAgent] Missing safeagent-dashboard-v0.2.0.tar."
  echo "[SafeAgent] Please download the latest deployment bundle again."
  exit 1
fi

echo "[SafeAgent] Loading API image..."
docker load -i safeagent-api-v0.2.0.tar

echo "[SafeAgent] Loading portal image..."
docker load -i safeagent-dashboard-v0.2.0.tar

echo "[SafeAgent] Starting containers..."
docker compose -f docker-compose.release.yml up -d

echo "[SafeAgent] Running database migrations..."
docker compose -f docker-compose.release.yml exec api python -m scripts.run_migrations

echo "[SafeAgent] Offline deployment completed successfully."
