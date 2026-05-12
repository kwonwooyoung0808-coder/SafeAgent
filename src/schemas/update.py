from __future__ import annotations

from pydantic import BaseModel


class ReleaseArtifact(BaseModel):
    name: str
    path: str
    kind: str


class ReleaseHistoryEntry(BaseModel):
    at: str
    version: str
    action: str
    status: str


class ReleaseManifestResponse(BaseModel):
    product: str
    channel: str
    current_version: str
    latest_version: str
    published_at: str
    requires_migration: bool
    priority: str
    recommended_install_mode: str
    artifacts: list[ReleaseArtifact]
    notes: list[str]
    history: list[ReleaseHistoryEntry]


class UpdateStatusResponse(BaseModel):
    product: str
    channel: str
    current_version: str
    latest_version: str
    update_available: bool
    published_at: str
    requires_migration: bool
    priority: str


class UpdateHistoryResponse(BaseModel):
    items: list[ReleaseHistoryEntry]
