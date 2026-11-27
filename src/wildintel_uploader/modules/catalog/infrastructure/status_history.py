"""The history of the states of the locations, the cameras and the SD cards of a research project, kept apart from its records in its
`status_history.json` (the project store); what a line is, and how the visits make them, is the domain's (domain.history).

What was kept before the history was has none: it is rebuilt from the visits kept (`rebuild`), the first time the history of a research project is
asked for, and again when it is asked."""
from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from wildintel_uploader.modules.catalog.domain import history
from wildintel_uploader.modules.catalog.domain.models import Location
from wildintel_uploader.modules.catalog.domain.ports import CatalogRepository, StatusHistory
from wildintel_uploader.modules.catalog.infrastructure.mapping import equipment_to_record, location_to_record
from wildintel_uploader.modules.catalog.infrastructure.visits import VisitsAsKept
from wildintel_uploader.shared import audit, storage

_rebuilding = threading.Lock()


class KeptStatusHistory(StatusHistory):
    """The history of the research projects of a collections folder; `repository` is where their records are kept, `visits` the visits of that
    folder as they are kept (infrastructure.visits.VisitsAsKept)."""

    def __init__(self, collections_dir: Path, repository: Callable[[], CatalogRepository], visits: Callable[[], VisitsAsKept]) -> None:
        self._root, self._repository, self._visits = collections_dir, repository, visits

    def _store(self) -> storage.ProjectStore:
        return storage.open_store(self._root)

    def checkpoint(self, project: str) -> Callable[[], None]:
        return storage.checkpoint(self._store, project, ["status_history"])

    def record_changes(self, project: str, kind: str, before: list[dict], after: list[dict], name_of: Callable[[dict], str],
                       match: Callable[[dict, list[dict]], dict | None]) -> int:
        """Writes a line for each of `after` whose status is not the one it had in `before`; says how many."""
        lines = history.changed_lines(kind, before, after, name_of, match, audit.now())
        if lines:
            store = self._store()
            store.write_records(project, "status_history", [*store.read_records(project, "status_history"), *lines])
        return len(lines)

    def record_location(self, project: str, before: Location | None, after: Location) -> None:
        self.record_changes(project, "locations", [location_to_record(before)] if before else [], [location_to_record(after)],
                            lambda record: str(record["location_id"]), (lambda item, old: old[0]) if before else (lambda item, old: None))

    def record_equipment(self, project: str, kind: str, before: list, after: list) -> None:
        self.record_changes(project, kind, [equipment_to_record(i, kind) for i in before], [equipment_to_record(i, kind) for i in after],
                            lambda r: str(r.get("label") or r.get("camera_id") or ""),
                            lambda item, old: next((r for r in old if r.get("id") and r.get("id") == item.get("id")), None))

    def lines(self, project: str, kind: str | None = None, name: str | None = None) -> list[dict[str, Any]]:
        """The lines of the history, the oldest first, of a kind and of one of them when they are given (the name is found ignoring case). A
        research project that has no history yet has it rebuilt from its visits first."""
        store = self._store()
        if not store.has_records(project, "status_history"):
            self.rebuild(project, only_if_missing=True)
        return [line for line in store.read_records(project, "status_history")
                if (kind is None or line.get("kind") == kind) and (name is None or str(line.get("name", "")).lower() == name.lower())]

    def rebuild(self, project: str, only_if_missing: bool = False) -> int:
        """Adds to the history what the visits kept say and it lacks — marked `reconstructed` —: nothing of it is overwritten nor deleted, and a
        line it already has is not written again, so it can be done again. The history is written even when there is nothing to add, so the first
        time is done once. `only_if_missing` does nothing when there is one. Says how many lines it added."""
        store = self._store()
        with _rebuilding:
            if only_if_missing and store.has_records(project, "status_history"):
                return 0
            lines = store.read_records(project, "status_history")
            recorded = {(line.get("kind"), str(line.get("name", "")).lower()) for line in lines if not line.get("reconstructed")}
            there = {history.same(line) for line in lines}
            repository = self._repository()
            locations = [r for r in (location_to_record(loc) for loc in repository.read_locations(project)) if not audit.is_deleted(r)]
            equipment = {kind: [r for r in (equipment_to_record(i, kind) for i in repository.read_equipment(project, kind)) if not audit.is_deleted(r)]
                         for kind in ("cameras", "sd_cards")}
            made = history.reconstructed_lines(locations, equipment, self._visits().visits(project), recorded, audit.now())
            new = [line for line in made if history.same(line) not in there]
            store.write_records(project, "status_history", history.in_order([*lines, *new]))
            return len(new)
