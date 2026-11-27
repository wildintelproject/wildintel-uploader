"""FastAPI router — fixing the dates and times of the images in a folder, against the period the visits give (module `modules.timefix`), at
/api/timefix as always. What it refuses is a 400."""
from __future__ import annotations

from collections.abc import Callable

from dishka.integrations.fastapi import DishkaSyncRoute, FromDishka
from fastapi import APIRouter, HTTPException

from wildintel_uploader.modules.timefix.domain.ports import TimeFixError, TimeFixService, VisitOfTheImages
from wildintel_uploader.modules.timefix.infrastructure.api_schemas import FolderRequest, RemoveRequest, ShiftRequest

router = APIRouter(prefix="/api/timefix", tags=["timefix"], route_class=DishkaSyncRoute)
TimeFix = FromDishka[TimeFixService]


def _visit(req: FolderRequest) -> VisitOfTheImages | None:
    if not (req.research_project_id and req.location_id and req.date and req.time):
        return None
    return VisitOfTheImages(req.research_project_id, req.location_id, req.date, req.time)


def _http(call: Callable[[], dict]) -> dict:
    try:
        return call()
    except TimeFixError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/timeline")
def timeline(req: FolderRequest, timefix: TimeFix) -> dict:
    """The folder's images in the camera's order, with their times, segments and the fixes made so far."""
    return _http(lambda: timefix.timeline(req.folder, _visit(req)))


@router.post("/shift")
def shift(req: ShiftRequest, timefix: TimeFix) -> dict:
    """Moves the date and time of a run of images by an offset; returns the timeline after it."""
    return _http(lambda: timefix.shift(req.folder, _visit(req), req.first, req.last, req.offset_seconds, req.reason))


@router.post("/remove")
def remove(req: RemoveRequest, timefix: TimeFix) -> dict:
    """Takes images whose time can't be made right out of the folder; returns the timeline after it."""
    return _http(lambda: timefix.remove(req.folder, _visit(req), req.names, req.reason))
