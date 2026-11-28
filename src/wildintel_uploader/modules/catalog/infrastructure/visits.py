"""What the catalog needs of the visits: whether a research project has visits, how many a location has and what the visits say against a status
asked for by hand — read from where the visits are kept, told with the catalog's own records (what the visits offer the catalog:
visits.domain.for_the_catalog) —, so that the catalog never needs the module of the visits, which needs the catalog."""
from __future__ import annotations

from collections.abc import Callable
from typing import cast

from wildintel_uploader.modules.catalog.domain.models import Location
from wildintel_uploader.modules.catalog.domain.ports import CatalogRepository, VisitHistory
from wildintel_uploader.modules.catalog.infrastructure.mapping import equipment_to_record, location_to_record, trapper_to_record
from wildintel_uploader.modules.visits.domain import for_the_catalog as the_visits
from wildintel_uploader.shared.storage import ProjectStore


def _seen(location: Location) -> the_visits.Location:
    """A location of the catalog as the visits see it: its record (the shapes are of the visits, the records are the catalog's)."""
    return cast(the_visits.Location, location_to_record(location))


class VisitsAsKept:
    """The visits of the research projects of a collections folder as they are kept (`store`), told with the records the catalog keeps
    (`repository`) — read only: what a visit kept by an earlier version would be written back as is left to the module of the visits."""

    def __init__(self, store: ProjectStore, repository: Callable[[], CatalogRepository]) -> None:
        self._store, self._repository = store, repository

    def _locations(self, project: str) -> list[the_visits.Location]:
        return [_seen(loc) for loc in self._repository().read_locations(project)]

    def visits(self, project: str, location_id: str | None = None) -> list[the_visits.Visit]:
        repository = self._repository()
        told = the_visits.told(cast(list[the_visits.Visit], self._store.read_records(project, "visits")), self._locations(project),
                               [cast(the_visits.Camera, equipment_to_record(i, "cameras")) for i in repository.read_equipment(project, "cameras")],
                               [cast(the_visits.SdCard, equipment_to_record(i, "sd_cards")) for i in repository.read_equipment(project, "sd_cards")],
                               [cast(the_visits.Trapper, trapper_to_record(t)) for t in repository.read_trappers()], project)
        return told if location_id is None else [v for v in told if str(v.get("location_id", "")).lower() == location_id.lower()]

    def unknown(self, project: str) -> list[the_visits.UnknownVisit]:
        return the_visits.unknown_told(cast(list[the_visits.UnknownVisit], self._store.read_records(project, "unknown_visits")), self._locations(project))


class StoredVisits(VisitHistory):
    def __init__(self, store: ProjectStore, visits: VisitsAsKept) -> None:
        self.store, self._visits = store, visits

    def has_visits(self, acronym: str) -> bool:
        return bool(self.store.read_records(acronym, "visits"))

    def visits_at(self, project: str, location_id: str) -> int:
        return len(self._visits.visits(project, location_id))

    def site_status_refusal(self, project: str, locations: list[Location], location: Location, wanted: str) -> str | None:
        return the_visits.site_status_refusal(self._visits.visits(project), self._visits.unknown(project), [_seen(loc) for loc in locations],
                                            _seen(location), wanted)

    def equipment_status_refusal(self, project: str, kind: str, item, wanted: str) -> str | None:
        visits = self._visits.visits(project)
        if kind == "cameras":
            return the_visits.camera_status_refusal(cast(the_visits.Camera, equipment_to_record(item, kind)), wanted, visits)
        return the_visits.card_status_refusal(cast(the_visits.SdCard, equipment_to_record(item, kind)), wanted, visits)
