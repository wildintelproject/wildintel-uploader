"""The use cases of the fixes of the dates: the period of the visit, when it is given; the timeline of the images; a run shifted, images taken
out — every fix written down, and the timeline after it. No second copy of the card is kept: a shift is undone by shifting back."""
from __future__ import annotations

import logging
from pathlib import Path

from wildintel_uploader.modules.timefix.domain import rules
from wildintel_uploader.modules.timefix.domain.ports import (
    Corrections, DateShifter, ImageDates, ImageFolder, Period, TimeFixError, TimeFixService, Tolerance, VisitOfTheImages, VisitsOfTheLocation,
)

logger = logging.getLogger(__name__)


class TimeFixUseCases(TimeFixService):
    def __init__(self, visits: VisitsOfTheLocation, folders: ImageFolder, dates: ImageDates, shifter: DateShifter, corrections: Corrections,
                 tolerance: Tolerance) -> None:
        self._visits, self._folders, self._dates, self._shifter = visits, folders, dates, shifter
        self._corrections, self._tolerance = corrections, tolerance

    def period(self, visit: VisitOfTheImages) -> Period:
        return rules.deployment_period(self._visits.visits(visit.research_project_id, visit.location_id), visit.research_project_id,
                                       visit.location_id, visit.date, visit.time)

    def _period(self, visit: VisitOfTheImages | None) -> Period | None:
        return self.period(visit) if visit is not None else None

    def _timeline(self, folder: Path, period: Period | None) -> dict:
        images = self._folders.images(folder)
        read = self._dates.dates(images)   # one run of ExifTool for all of them (#227)
        return rules.timeline(str(folder), [p.name for p in images], [read.get(p) for p in images], period, self._tolerance.hours(),
                              self._corrections.read(folder))

    def timeline(self, folder: str, visit: VisitOfTheImages | None = None) -> dict:
        period = self._period(visit)
        return self._timeline(self._folders.open(folder), period)

    def shift(self, folder: str, visit: VisitOfTheImages | None, first: str, last: str | None, offset_seconds: int, reason: str = "") -> dict:
        period = self._period(visit)
        path = self._folders.open(folder)
        if not offset_seconds:
            raise TimeFixError("An offset of 0 changes nothing.")
        images = self._folders.images(path)
        start, end = rules.run_of([p.name for p in images], first, last)
        run = images[start:end + 1]
        self._shifter.shift(path, run, offset_seconds)
        self._corrections.write(path, {"action": "shift", "first": run[0].name, "last": run[-1].name, "count": len(run),
                                       "offset_seconds": offset_seconds, "reason": reason.strip() or None})
        logger.info("%s: %d image(s) from %s shifted by %d s", path.name, len(run), run[0].name, offset_seconds)
        return self._timeline(path, period)

    def remove(self, folder: str, visit: VisitOfTheImages | None, names: list[str], reason: str = "") -> dict:
        period = self._period(visit)
        path = self._folders.open(folder)
        present = {p.name: p for p in self._folders.images(path)}
        chosen = rules.images_to_remove(list(present), names)
        self._folders.delete([present[n] for n in chosen])
        self._corrections.write(path, {"action": "remove", "names": chosen, "count": len(chosen), "reason": reason.strip() or None})
        logger.info("%s: %d image(s) removed for their time", path.name, len(chosen))
        return self._timeline(path, period)
