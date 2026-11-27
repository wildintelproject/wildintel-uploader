"""What the catalog needs of the visits and of the history of the states: whether a research project has visits, how many a location has and what
the visits say against a status asked for by hand — the visits through their contract, their rules from their domain (refusals) —, and the lines
of the history of the states."""
from __future__ import annotations

from pathlib import Path

from typing import Any

from wildintel_uploader.modules.catalog.domain.models import Location
from wildintel_uploader.modules.catalog.domain.ports import StatusHistory, VisitHistory
from wildintel_uploader.modules.catalog.infrastructure.mapping import equipment_to_record, location_to_record
from wildintel_uploader.modules.visits.domain import refusals
from wildintel_uploader.shared.storage import ProjectStore


class StoredVisits(VisitHistory):
    def __init__(self, store: ProjectStore, collections_dir: Path) -> None:
        self.store, self.collections_dir = store, collections_dir

    def has_visits(self, acronym: str) -> bool:
        return bool(self.store.read_records(acronym, "visits"))

    def _visits(self):
        """The visits of this collections folder — through their contract —, from where the app is put together."""
        from wildintel_uploader.entrypoints import wiring
        return wiring.build_visits(self.collections_dir)

    def visits_at(self, project: str, location_id: str) -> int:
        return len(self._visits().visits(project, location_id))

    def site_status_refusal(self, project: str, locations: list[Location], location: Location, wanted: str) -> str | None:
        visits = self._visits()
        return refusals.site_status_refusal(visits.visits(project), visits.unknown(project), [location_to_record(loc) for loc in locations],
                                            location_to_record(location), wanted)

    def equipment_status_refusal(self, project: str, kind: str, item, wanted: str) -> str | None:
        refusal = refusals.camera_status_refusal if kind == "cameras" else refusals.card_status_refusal
        return refusal(equipment_to_record(item, kind), wanted, self._visits().visits(project))


class StoredStatusHistory(StatusHistory):
    def __init__(self, collections_dir: Path) -> None:
        self.collections_dir = collections_dir

    def record_location(self, project: str, before: Location | None, after: Location) -> None:
        from wildintel_uploader.modules.catalog.infrastructure import status_history
        status_history.record_changes(self.collections_dir, project, "locations", [location_to_record(before)] if before else [],
                                      [location_to_record(after)], lambda record: str(record["location_id"]),
                                      (lambda item, old: old[0]) if before else (lambda item, old: None))

    def record_equipment(self, project: str, kind: str, before: list, after: list) -> None:
        from wildintel_uploader.modules.catalog.infrastructure import status_history
        status_history.record_changes(self.collections_dir, project, kind, [equipment_to_record(i, kind) for i in before],
                                      [equipment_to_record(i, kind) for i in after], lambda r: str(r.get("label") or r.get("camera_id") or ""),
                                      lambda item, old: next((r for r in old if r.get("id") and r.get("id") == item.get("id")), None))

    def lines(self, project: str, kind: str | None, name: str | None) -> list[dict[str, Any]]:
        from wildintel_uploader.modules.catalog.infrastructure import status_history
        return status_history.list_history(self.collections_dir, project, kind, name)

    def rebuild(self, project: str) -> int:
        from wildintel_uploader.modules.catalog.infrastructure import status_history
        return status_history.rebuild(self.collections_dir, project)
