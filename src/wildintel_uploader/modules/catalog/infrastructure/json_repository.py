"""CatalogRepository over the records of the collections folder (shared.storage — JSON files today): the people are a global record, beside the
research projects; each research project has its folder, named by its acronym, which holds its record and, besides, its collections."""
from __future__ import annotations

from collections.abc import Callable

from wildintel_uploader.modules.catalog.domain.models import Location, ResearchProject, Role, Trapper
from wildintel_uploader.modules.catalog.domain.ports import CatalogRepository
from wildintel_uploader.modules.catalog.infrastructure.mapping import (
    equipment_from_record, equipment_to_record, location_from_record, location_to_record, project_from_record, project_to_record, role_from_record,
    role_to_record, trapper_from_record, trapper_to_record,
)
from wildintel_uploader.shared import storage
from wildintel_uploader.shared.storage import ProjectStore, StorageError


class StoreCatalogRepository(CatalogRepository):
    def __init__(self, store: ProjectStore) -> None:
        self.store = store

    def checkpoint(self, project: str) -> Callable[[], None]:
        records = storage.checkpoint(lambda: self.store, project, ["locations", "cameras", "sd_cards", "roles"])
        trappers = self.store.read_global("trappers")

        def put_back() -> None:
            records()
            self.store.write_global("trappers", trappers)
        return put_back

    def read_trappers(self) -> list[Trapper]:
        return [trapper_from_record(r) for r in self.store.read_global("trappers")]

    def write_trappers(self, trappers: list[Trapper]) -> None:
        self.store.write_global("trappers", [trapper_to_record(t) for t in trappers])

    def read_projects(self) -> list[ResearchProject]:
        return [project_from_record(r) for r in self.store.list_projects()]

    def read_project(self, acronym: str) -> ResearchProject | None:
        record = self.store.get_project(acronym)
        return project_from_record(record) if record is not None else None

    def add_project(self, project: ResearchProject) -> None:
        self.store.add_project(project_to_record(project))

    def save_project(self, project: ResearchProject) -> None:
        self.store.save_project(project.acronym, project_to_record(project))

    def files_of(self, acronym: str) -> set[str]:
        return self.store.owned_names(acronym)

    def read_locations(self, project: str) -> list[Location]:
        try:
            return [location_from_record(r, project) for r in self.store.read_records(project, "locations")]
        except StorageError:   # a research project id that can't be a folder name has no locations
            return []

    def write_locations(self, project: str, locations: list[Location]) -> None:
        self.store.write_records(project, "locations", [location_to_record(loc) for loc in locations])

    def read_equipment(self, project: str, kind: str) -> list:
        try:
            return [equipment_from_record(r, kind, project) for r in self.store.read_records(project, kind)]
        except StorageError:
            return []

    def write_equipment(self, project: str, kind: str, items: list) -> None:
        self.store.write_records(project, kind, [equipment_to_record(i, kind) for i in items])

    def read_roles(self, project: str) -> list[Role]:
        try:
            return [role_from_record(r, project) for r in self.store.read_records(project, "roles")]
        except StorageError:
            return []

    def write_roles(self, project: str, roles: list[Role]) -> None:
        self.store.write_records(project, "roles", [role_to_record(r) for r in roles])
