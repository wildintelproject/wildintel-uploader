"""The web API of the backups as JSON — what the requests send, for entrypoints/api/backup.py."""
from __future__ import annotations

from typing import Any

from wildintel_uploader.shared.answers import Answer

from pydantic import BaseModel, Field


class ProjectInfoRequest(BaseModel):
    research_project_id: str


class CreateBackupRequest(BaseModel):
    # The folder the backup is made in; with none, it is made to be downloaded by the browser: see /download.
    dest_dir: str | None = None
    settings: bool = False
    research_project_id: str | None = None
    project_files: bool = False
    visits: bool = False
    deployments: list[str] = Field(default_factory=list)
    images: bool = False


class ReadBackupRequest(BaseModel):
    path: str


class RestoreRequest(BaseModel):
    path: str
    settings: bool = False
    project_files: bool = False
    visits: bool = False
    deployments: list[str] = Field(default_factory=list)
    images: bool = False
    replace: bool = False


# ── what the routes answer (#248) ──


class ProjectInfoAnswer(Answer):
    """What POST /api/backup/project-info answers."""
    research_project_id: str | None = None
    locations: int | None = None
    cameras: int | None = None
    sd_cards: int | None = None
    visits: int | None = None
    collections: list[Any] | None = None


class ReadAnswer(Answer):
    """What POST /api/backup/read answers."""
    manifest: dict[str, Any] | None = None
    here: dict[str, Any] | None = None
    has_images: dict[str, Any] | None = None


class PickedFile(Answer):
    path: str | None = None
