$ErrorActionPreference = "Stop"

$apiImage = if ($env:SAFEAGENT_API_IMAGE) { $env:SAFEAGENT_API_IMAGE } else { "ghcr.io/our-org/safeagent:v0.2.0" }
$portalImage = if ($env:SAFEAGENT_FRONTEND_IMAGE) { $env:SAFEAGENT_FRONTEND_IMAGE } else { "ghcr.io/our-org/safeagent-portal:v0.2.0" }
$apiTar = "safeagent-api-v0.2.0.tar"
$portalTar = "safeagent-portal-v0.2.0.tar"

Write-Host "[SafeAgent] API 이미지를 가져옵니다: $apiImage"
docker pull $apiImage
docker save -o $apiTar $apiImage

Write-Host "[SafeAgent] 프론트 이미지를 가져옵니다: $portalImage"
docker pull $portalImage
docker save -o $portalTar $portalImage

Write-Host "[SafeAgent] 오프라인 이미지 준비가 완료되었습니다."
