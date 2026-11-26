"""What the catalog needs of the visits and of the history of the states, over the code of before (core/services): whether a research project has
visits, how many a location has, what the visits say against a status asked for by hand (visit_rules), and the lines of the history of the states
(status_history). Once the visits are a module of their own, these ask its contract instead."""
from __future__ import annotations

from pathlib import Path

from wildintel_uploader.modules.catalog.domain.models import Location
from wildintel_uploader.modules.catalog.domain.ports import StatusHistory, VisitHistory
from wildintel_uploader.modules.catalog.infrastructure.mapping import location_to_record
from wildintel_uploader.shared.storage import ProjectStore


class StoredVisits(VisitHistory):
    def __init__(self, store: ProjectStore, collections_dir: Path) -> None:
        self.store, self.collections_dir = store, collections_dir

    def has_visits(self, acronym: str) -> bool:
        return bool(self.store.read_records(acronym, "visits"))

    def visits_at(self, project: str, location_id: str) -> int:
        from wildintel_uploader.core.services import local_folder_service   # here: it is code of before that uses the catalog
        return len(local_folder_service.list_visits(self.collections_dir, project, location_id))

    def site_status_refusal(self, project: str, locations: list[Location], location: Location, wanted: str) -> str | None:
        from wildintel_uploader.core.services import local_folder_service
        return local_folder_service._site_status_refusal(self.collections_dir, project, [location_to_record(loc) for loc in locations],
                                                         location_to_record(location), wanted)


class StoredStatusHistory(StatusHistory):
    def __init__(self, collections_dir: Path) -> None:
        self.collections_dir = collections_dir

    def record_location(self, project: str, before: Location | None, after: Location) -> None:
        from wildintel_uploader.core.services import status_history
        status_history.record_changes(self.collections_dir, project, "locations", [location_to_record(before)] if before else [],
                                      [location_to_record(after)], lambda record: str(record["location_id"]),
                                      (lambda item, old: old[0]) if before else (lambda item, old: None))
