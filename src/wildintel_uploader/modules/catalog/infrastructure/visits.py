"""VisitHistory over the visits as they are kept today (shared.storage): the catalog reads only whether there are any. Once the visits are a module
of their own, this asks its contract instead."""
from __future__ import annotations

from wildintel_uploader.modules.catalog.domain.ports import VisitHistory
from wildintel_uploader.shared.storage import ProjectStore


class StoredVisits(VisitHistory):
    def __init__(self, store: ProjectStore) -> None:
        self.store = store

    def has_visits(self, acronym: str) -> bool:
        return bool(self.store.read_records(acronym, "visits"))
