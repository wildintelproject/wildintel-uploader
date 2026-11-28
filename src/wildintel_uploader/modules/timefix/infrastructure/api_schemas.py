"""The web API of the fixes of the dates as JSON — what the requests send, for entrypoints/api/timefix.py."""
from __future__ import annotations

from typing import Any
from pydantic import Field

from wildintel_uploader.shared.answers import Answer

from typing import Optional

from pydantic import BaseModel


class FolderRequest(BaseModel):
    """The folder with the images and, to check their dates against a deployment's period, the visit that left the camera."""
    folder: str
    research_project_id: Optional[str] = None
    location_id: Optional[str] = None
    date: Optional[str] = None
    time: Optional[str] = None


class ShiftRequest(FolderRequest):
    first: str
    last: Optional[str] = None
    offset_seconds: int
    reason: str = ""


class RemoveRequest(FolderRequest):
    names: list[str]
    reason: str = ""


# ── what the routes answer (#248) ──


class TimelineAnswer(Answer):
    """What POST /api/timefix/timeline answers."""
    folder: str | None = None
    period: dict[str, Any] | None = None
    tolerance_hours: float | None = None
    images: list[Any] | None = None
    segments: list[Any] | None = None
    undated: list[Any] | None = None
    outside: int | None = None
    problems: list[Any] | None = None
    ok: bool | None = None
    corrections: list[Any] | None = None
