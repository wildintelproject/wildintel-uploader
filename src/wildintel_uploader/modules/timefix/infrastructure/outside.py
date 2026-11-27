"""What the fixes of the dates take from other modules: the visits of a location — through their contract —, and the tolerance of the settings."""
from __future__ import annotations

from collections.abc import Callable

from wildintel_uploader.modules.settings.domain.ports import StoredSettings
from wildintel_uploader.modules.timefix.domain.ports import TimeFixError, Tolerance, VisitsOfTheLocation
from wildintel_uploader.modules.visits.domain.models import VisitsError
from wildintel_uploader.modules.visits.domain.ports import VisitsService


class VisitsThroughTheirContract(VisitsOfTheLocation):
    def __init__(self, visits: Callable[[], VisitsService]) -> None:
        self._visits = visits

    def visits(self, research_project_id: str, location_id: str) -> list[dict]:
        try:
            return self._visits().visits(research_project_id, location_id)
        except VisitsError as exc:
            raise TimeFixError(exc.message) from exc


class ToleranceInUse(Tolerance):
    def __init__(self, settings: StoredSettings) -> None:
        self._settings = settings

    def hours(self) -> float:
        return self._settings.load_settings().POSTVALIDATION.tolerance_hours
