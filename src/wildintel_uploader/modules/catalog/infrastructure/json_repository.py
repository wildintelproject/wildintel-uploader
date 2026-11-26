"""CatalogRepository over the records of the collections folder (shared.storage — JSON files today): the people are a global record, beside the
research projects."""
from __future__ import annotations

from wildintel_uploader.modules.catalog.domain.models import Trapper
from wildintel_uploader.modules.catalog.domain.ports import CatalogRepository
from wildintel_uploader.modules.catalog.infrastructure.mapping import trapper_from_record, trapper_to_record
from wildintel_uploader.shared.storage import ProjectStore


class StoreCatalogRepository(CatalogRepository):
    def __init__(self, store: ProjectStore) -> None:
        self.store = store

    def read_trappers(self) -> list[Trapper]:
        return [trapper_from_record(r) for r in self.store.read_global("trappers")]

    def write_trappers(self, trappers: list[Trapper]) -> None:
        self.store.write_global("trappers", [trapper_to_record(t) for t in trappers])
