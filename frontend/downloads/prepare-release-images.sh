#!/usr/bin/env sh
set -eu

API_IMAGE="${SAFEAGENT_API_IMAGE:-ghcr.io/our-org/safeagent:v0.2.0}"
PORTAL_IMAGE="${SAFEAGENT_FRONTEND_IMAGE:-ghcr.io/our-org/safeagent-portal:v0.2.0}"

echo "[SafeAgent] API 이미지를 가져옵니다: ${API_IMAGE}"
docker pull "${API_IMAGE}"
docker save -o safeagent-api-v0.2.0.tar "${API_IMAGE}"

echo "[SafeAgent] 프론트 이미지를 가져옵니다: ${PORTAL_IMAGE}"
docker pull "${PORTAL_IMAGE}"
docker save -o safeagent-portal-v0.2.0.tar "${PORTAL_IMAGE}"

echo "[SafeAgent] 오프라인 이미지 준비가 완료되었습니다."
