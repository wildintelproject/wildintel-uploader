"""What the catalog needs of the visits: whether a research project has visits, how many a location has and what the visits say against a status
asked for by hand — read from where the visits are kept, told with the catalog's own records (the visits' rules from their domain: references,
refusals) —, so that the catalog never needs the module of the visits, which needs the catalog."""
from __future__ import annotations

from collections.abc import Callable

from wildintel_uploader.modules.catalog.domain.models import Location
from wildintel_uploader.modules.catalog.domain.ports import CatalogRepository, VisitHistory
from wildintel_uploader.modules.catalog.infrastructure.mapping import equipment_to_record, location_to_record, trapper_to_record
from wildintel_uploader.modules.visits.domain import references, refusals
from wildintel_uploader.shared.storage import ProjectStore


class VisitsAsKept:
    """The visits of the research projects of a collections folder as they are kept (`store`), told with the records the catalog keeps
    (`repository`) — read only: what a visit kept by an earlier version would be written back as is left to the module of the visits."""

    def __init__(self, store: ProjectStore, repository: Callable[[], CatalogRepository]) -> None:
        self._store, self._repository = store, repository

    def _locations(self, project: str) -> list[dict]:
        return [location_to_record(loc) for loc in self._repository().read_locations(project)]

    def _refs(self, project: str) -> references.Refs:
        repository = self._repository()
        return references.Refs(self._locations(project),
                               [equipment_to_record(i, "cameras") for i in repository.read_equipment(project, "cameras")],
                               [equipment_to_record(i, "sd_cards") for i in repository.read_equipment(project, "sd_cards")],
                               [trapper_to_record(t) for t in repository.read_trappers()])

    def visits(self, project: str, location_id: str | None = None) -> list[dict]:
        _, told = references.read_kept(self._store.read_records(project, "visits"), self._refs(project), project)
        return told if location_id is None else [v for v in told if str(v.get("location_id", "")).lower() == location_id.lower()]

    def unknown(self, project: str) -> list[dict]:
        return references.unknown_told(self._store.read_records(project, "unknown_visits"), self._locations(project))


class StoredVisits(VisitHistory):
    def __init__(self, store: ProjectStore, visits: VisitsAsKept) -> None:
        self.store, self._visits = store, visits

    def has_visits(self, acronym: str) -> bool:
        return bool(self.store.read_records(acronym, "visits"))

    def visits_at(self, project: str, location_id: str) -> int:
        return len(self._visits.visits(project, location_id))

    def site_status_refusal(self, project: str, locations: list[Location], location: Location, wanted: str) -> str | None:
        return refusals.site_status_refusal(self._visits.visits(project), self._visits.unknown(project), [location_to_record(loc) for loc in locations],
                                            location_to_record(location), wanted)

    def equipment_status_refusal(self, project: str, kind: str, item, wanted: str) -> str | None:
        refusal = refusals.camera_status_refusal if kind == "cameras" else refusals.card_status_refusal
        return refusal(equipment_to_record(item, kind), wanted, self._visits.visits(project))
