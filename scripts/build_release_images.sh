#!/usr/bin/env sh
set -eu

VERSION="${SAFEAGENT_RELEASE_VERSION:-v0.2.0}"
API_IMAGE="safeagent-api-local:${VERSION}"
DASHBOARD_IMAGE="safeagent-dashboard-local:${VERSION}"
ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
DOWNLOADS_DIR="${ROOT_DIR}/frontend/downloads"
API_TAR="${DOWNLOADS_DIR}/safeagent-api-${VERSION}.tar"
DASHBOARD_TAR="${DOWNLOADS_DIR}/safeagent-dashboard-${VERSION}.tar"

mkdir -p "${DOWNLOADS_DIR}"

echo "[SafeAgent] API 이미지를 로컬에서 빌드합니다: ${API_IMAGE}"
docker build -t "${API_IMAGE}" "${ROOT_DIR}"

echo "[SafeAgent] 대시보드 이미지를 로컬에서 빌드합니다: ${DASHBOARD_IMAGE}"
docker build -t "${DASHBOARD_IMAGE}" "${ROOT_DIR}/sys-frontend"

echo "[SafeAgent] API 이미지를 tar로 저장합니다: ${API_TAR}"
docker save -o "${API_TAR}" "${API_IMAGE}"

echo "[SafeAgent] 대시보드 이미지를 tar로 저장합니다: ${DASHBOARD_TAR}"
docker save -o "${DASHBOARD_TAR}" "${DASHBOARD_IMAGE}"

echo "[SafeAgent] 로컬 배포 이미지 준비가 완료되었습니다."
