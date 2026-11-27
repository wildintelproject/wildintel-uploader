"""What the fixes of the dates take from other modules: the visits of a location — through their contract —, and the tolerance of the settings."""
from __future__ import annotations

from typing import cast
from typing import Any
from collections.abc import Callable

from wildintel_uploader.modules.timefix.domain.ports import TimeFixError, Tolerance, VisitsOfTheLocation
from wildintel_uploader.modules.visits.domain.models import VisitsError
from wildintel_uploader.modules.visits.domain.ports import VisitsService


class VisitsThroughTheirContract(VisitsOfTheLocation):
    def __init__(self, visits: Callable[[], VisitsService]) -> None:
        self._visits = visits

    def visits(self, research_project_id: str, location_id: str) -> list[dict]:
        try:
            return cast(list[dict], self._visits().visits(research_project_id, location_id))   # the timefix reads a visit's date and time
        except VisitsError as exc:
            raise TimeFixError(exc.message) from exc


class ToleranceInUse(Tolerance):
    """The tolerance POSTVALIDATION says — `postvalidation` gives it, asked each time."""

    def __init__(self, postvalidation: Callable[[], Any]) -> None:
        self._postvalidation = postvalidation

    def hours(self) -> float:
        return self._postvalidation().tolerance_hours
