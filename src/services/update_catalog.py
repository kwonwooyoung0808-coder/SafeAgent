from __future__ import annotations

import json
from pathlib import Path

from fastapi import HTTPException, status

from src.core.config import get_settings
from src.schemas.update import (
    ReleaseManifestResponse,
    UpdateHistoryResponse,
    UpdateStatusResponse,
)


def _resolve_path(raw_path: str) -> Path:
    candidate = Path(raw_path)
    if candidate.is_absolute():
        return candidate
    return Path.cwd() / candidate


def load_release_manifest() -> ReleaseManifestResponse:
    settings = get_settings()
    manifest_path = _resolve_path(settings.update_manifest_path)
    if not manifest_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"release_manifest_not_found: {manifest_path}",
        )

    with manifest_path.open("r", encoding="utf-8") as fp:
        payload = json.load(fp)
    return ReleaseManifestResponse.model_validate(payload)


def get_update_status() -> UpdateStatusResponse:
    manifest = load_release_manifest()
    return UpdateStatusResponse(
        product=manifest.product,
        channel=manifest.channel,
        current_version=manifest.current_version,
        latest_version=manifest.latest_version,
        update_available=manifest.latest_version != manifest.current_version,
        published_at=manifest.published_at,
        requires_migration=manifest.requires_migration,
        priority=manifest.priority,
    )


def get_update_history() -> UpdateHistoryResponse:
    manifest = load_release_manifest()
    return UpdateHistoryResponse(items=manifest.history)


def get_release_bundle_path() -> Path:
    settings = get_settings()
    bundle_path = _resolve_path(settings.update_bundle_path)
    if not bundle_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"release_bundle_not_found: {bundle_path}",
        )
    return bundle_path
