$ErrorActionPreference = "Stop"

$version = if ($env:SAFEAGENT_RELEASE_VERSION) { $env:SAFEAGENT_RELEASE_VERSION } else { "v0.2.0" }
$apiImage = "safeagent-api-local:$version"
$portalImage = "safeagent-portal-local:$version"
$downloadsDir = Join-Path $PSScriptRoot "..\frontend\downloads"
$apiTar = Join-Path $downloadsDir "safeagent-api-$version.tar"
$portalTar = Join-Path $downloadsDir "safeagent-portal-$version.tar"

New-Item -ItemType Directory -Force -Path $downloadsDir | Out-Null

Write-Host "[SafeAgent] API 이미지를 로컬에서 빌드합니다: $apiImage"
docker build -t $apiImage (Join-Path $PSScriptRoot "..")

Write-Host "[SafeAgent] 프론트 이미지를 로컬에서 빌드합니다: $portalImage"
docker build -t $portalImage (Join-Path $PSScriptRoot "..\frontend")

Write-Host "[SafeAgent] API 이미지를 tar로 저장합니다: $apiTar"
docker save -o $apiTar $apiImage

Write-Host "[SafeAgent] 프론트 이미지를 tar로 저장합니다: $portalTar"
docker save -o $portalTar $portalImage

Write-Host "[SafeAgent] 로컬 배포 이미지 준비가 완료되었습니다."
