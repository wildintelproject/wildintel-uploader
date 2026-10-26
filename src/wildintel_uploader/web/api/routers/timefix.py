"""FastAPI router — fixing the dates and times of the images in a folder, against the period the visits give (see services.timefix_service)."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from wildintel_uploader.core.services import timefix_service

router = APIRouter(prefix="/api/timefix", tags=["timefix"])


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


def _period(req: FolderRequest):
    if not (req.research_project_id and req.location_id and req.date and req.time):
        return None
    return timefix_service.visit_period(req.research_project_id, req.location_id, req.date, req.time)


def _call(function, req: FolderRequest, *args):
    try:
        return function(req.folder, _period(req), *args)
    except timefix_service.TimeFixError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/timeline")
def timeline(req: FolderRequest) -> dict:
    """The folder's images in the camera's order, with their times, segments and the fixes made so far."""
    return _call(timefix_service.timeline, req)


@router.post("/shift")
def shift(req: ShiftRequest) -> dict:
    """Moves the date and time of a run of images by an offset; returns the timeline after it."""
    return _call(timefix_service.shift, req, req.first, req.last, req.offset_seconds, req.reason)


@router.post("/remove")
def remove(req: RemoveRequest) -> dict:
    """Takes images whose time can't be made right out of the folder; returns the timeline after it."""
    return _call(timefix_service.remove, req, req.names, req.reason)
