"""The web API of the fixes of the dates as JSON — what the requests send, for entrypoints/api/timefix.py."""
from __future__ import annotations

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
