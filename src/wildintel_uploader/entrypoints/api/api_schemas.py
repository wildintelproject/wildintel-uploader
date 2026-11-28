"""What the routes of the app itself answer — its health and version, and the folders and tools of the desktop (#248): they belong to no module."""
from __future__ import annotations

from typing import Any

from pydantic import Field

from wildintel_uploader.shared.answers import Answer


# ── what the routes answer (#248) ──


class ExiftoolAnswer(Answer):
    """What GET /api/deployment-import/exiftool answers."""
    available: bool | None = None
    path: str | None = None


class BrowseFolderAnswer(Answer):
    """What POST /api/deployment-import/browse-folder answers."""
    path: str | None = None


class OpenFolderAnswer(Answer):
    """What POST /api/deployment-import/open-folder answers."""
    opened: str | None = None


class HealthAnswer(Answer):
    """What GET /api/health answers."""
    status: str | None = None


class CheckForUpdateAnswer(Answer):
    """What GET /api/version/check answers."""
    current: str | None = None
    latest: str | None = None
    update_available: bool | None = None
    release_url: str | None = None
    download_url: str | None = None
    error: str | None = None


class VersionAnswer(Answer):
    current: str
