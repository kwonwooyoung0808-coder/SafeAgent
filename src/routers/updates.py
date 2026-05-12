from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import FileResponse

from src.schemas.update import (
    ReleaseManifestResponse,
    UpdateHistoryResponse,
    UpdateStatusResponse,
)
from src.services.update_catalog import (
    get_release_bundle_path,
    get_update_history,
    get_update_status,
    load_release_manifest,
)

router = APIRouter(prefix="/v1/updates", tags=["updates"])


@router.get("/status", response_model=UpdateStatusResponse)
def updates_status() -> UpdateStatusResponse:
    return get_update_status()


@router.get("/check", response_model=ReleaseManifestResponse)
def updates_check() -> ReleaseManifestResponse:
    return load_release_manifest()


@router.get("/history", response_model=UpdateHistoryResponse)
def updates_history() -> UpdateHistoryResponse:
    return get_update_history()


@router.get("/bundle")
def updates_bundle() -> FileResponse:
    bundle_path = get_release_bundle_path()
    return FileResponse(
        bundle_path,
        media_type="application/zip",
        filename=bundle_path.name,
    )
