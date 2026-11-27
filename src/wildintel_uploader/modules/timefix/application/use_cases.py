"""The use cases of the fixes of the dates: the period of the visit, when it is given, and what is done to the images."""
from __future__ import annotations

from wildintel_uploader.modules.timefix.domain.ports import Period, TimedImages, TimeFixService, VisitOfTheImages, VisitPeriods


class TimeFixUseCases(TimeFixService):
    def __init__(self, periods: VisitPeriods, images: TimedImages) -> None:
        self._periods, self._images = periods, images

    def _period(self, visit: VisitOfTheImages | None) -> Period | None:
        return self._periods.period(visit) if visit is not None else None

    def timeline(self, folder: str, visit: VisitOfTheImages | None = None) -> dict:
        return self._images.timeline(folder, self._period(visit))

    def shift(self, folder: str, visit: VisitOfTheImages | None, first: str, last: str | None, offset_seconds: int, reason: str = "") -> dict:
        return self._images.shift(folder, self._period(visit), first, last, offset_seconds, reason)

    def remove(self, folder: str, visit: VisitOfTheImages | None, names: list[str], reason: str = "") -> dict:
        return self._images.remove(folder, self._period(visit), names, reason)
