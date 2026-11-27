"""The ports of the fixes of the dates over the code of before (timefix_service): ExifTool shifts the dates, a log beside the images writes the
fixes down. What it refuses is the module's TimeFixError, with its words."""
from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from wildintel_uploader.modules.timefix.domain.ports import Period, TimedImages, TimeFixError, VisitOfTheImages, VisitPeriods

T = TypeVar("T")


def _old():
    from wildintel_uploader.core.services import timefix_service
    return timefix_service


def _ours(call: Callable[[], T]) -> T:
    try:
        return call()
    except _old().TimeFixError as exc:
        raise TimeFixError(str(exc)) from exc


class PeriodsOfTheVisits(VisitPeriods):
    def period(self, visit: VisitOfTheImages) -> Period:
        return _ours(lambda: _old().visit_period(visit.research_project_id, visit.location_id, visit.date, visit.time))


class ImagesWithExifTool(TimedImages):
    def timeline(self, folder: str, period: Period | None) -> dict:
        return _ours(lambda: _old().timeline(folder, period))

    def shift(self, folder: str, period: Period | None, first: str, last: str | None, offset_seconds: int, reason: str) -> dict:
        return _ours(lambda: _old().shift(folder, period, first, last, offset_seconds, reason))

    def remove(self, folder: str, period: Period | None, names: list[str], reason: str) -> dict:
        return _ours(lambda: _old().remove(folder, period, names, reason))
