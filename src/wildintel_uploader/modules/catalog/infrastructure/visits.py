"""What the catalog needs of the visits and of the history of the states: whether a research project has visits, how many a location has and what
the visits say against a status asked for by hand — the visits through their contract, their rules from their domain (refusals) —, and the lines
of the history of the states."""
from __future__ import annotations



from wildintel_uploader.modules.catalog.domain.models import Location
from wildintel_uploader.modules.catalog.domain.ports import VisitHistory
from wildintel_uploader.modules.catalog.infrastructure.mapping import equipment_to_record, location_to_record
from wildintel_uploader.modules.visits.domain import refusals
from wildintel_uploader.shared.storage import ProjectStore
from collections.abc import Callable

from wildintel_uploader.modules.visits.domain.ports import VisitsService


class StoredVisits(VisitHistory):
    def __init__(self, store: ProjectStore, visits: Callable[[], VisitsService]) -> None:
        self.store, self._visits = store, visits   # the visits of the same collections folder, through their contract

    def has_visits(self, acronym: str) -> bool:
        return bool(self.store.read_records(acronym, "visits"))

    def visits_at(self, project: str, location_id: str) -> int:
        return len(self._visits().visits(project, location_id))

    def site_status_refusal(self, project: str, locations: list[Location], location: Location, wanted: str) -> str | None:
        visits = self._visits()
        return refusals.site_status_refusal(visits.visits(project), visits.unknown(project), [location_to_record(loc) for loc in locations],
                                            location_to_record(location), wanted)

    def equipment_status_refusal(self, project: str, kind: str, item, wanted: str) -> str | None:
        refusal = refusals.camera_status_refusal if kind == "cameras" else refusals.card_status_refusal
        return refusal(equipment_to_record(item, kind), wanted, self._visits().visits(project))
