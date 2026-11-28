"""The records of the catalog as they are kept — the research projects, their locations, cameras and SD cards, and the people and their roles as
a backup holds them —, for a backup only (CatalogRecordStore, see domain.records)."""
from __future__ import annotations

import logging
from collections.abc import Callable
from contextlib import contextmanager

from wildintel_uploader.modules.catalog.domain.models import Audit, CatalogError, Role, UnknownCamera, UnknownLocation, UnknownProject
from wildintel_uploader.modules.catalog.domain.ports import CatalogRepository, CatalogService
from wildintel_uploader.modules.catalog.domain.records import CatalogRecordStore
from wildintel_uploader.modules.catalog.infrastructure.mapping import (
    equipment_from_record, equipment_to_record, location_from_record, location_to_record, project_from_record, project_to_record, role_to_record,
    trapper_from_record, trapper_to_record,
)
from wildintel_uploader.shared import storage

logger = logging.getLogger(__name__)

RESEARCH_PROJECT_METADATA_FILE = "research_project.json"
LOCATIONS_FILE = "locations.json"
VISITS_FILE = "visits.json"
UNKNOWN_FILE = "unknown_visits.json"
# The uploads that were tried and failed — one record for each deployment and destination: an upload is planned until it is done, and a failed one is tried again.
UPLOAD_FAILURES_FILE = "upload_failures.json"
CAMERAS_FILE = "cameras.json"
SD_CARDS_FILE = "sd_cards.json"

# What is kept of the research projects — the projects, their locations, visits, cameras and SD cards — goes through `storage` (see shared.storage): the JSON files of the
# collections folder today, whatever backend is registered tomorrow. This module has the rules; the store only keeps. What is not a record — the images, and what is
# written beside them — stays a file of the collections folder.
LocalFolderError = storage.StorageError   # a research project or location can't be read or saved in the collections folder


class RecordStoreOf(CatalogRecordStore):
    """The records of the catalog of a collections folder as its repository keeps them — round the rules of the catalog, which would date them
    anew: what a backup copies and restores."""

    def __init__(self, repository: Callable[[], CatalogRepository], catalog: Callable[[], CatalogService]) -> None:
        """`repository` keeps the records as they are; `catalog` is the catalog, for the people and the roles, which go through its rules."""
        self._repository, self._catalog = repository, catalog

    # the people and the roles, as a backup holds them — by the rules of the catalog: a person is known by its username, a role by the name of
    # its person, whatever ids they have here

    def trappers(self) -> list[dict]:
        """The people, those that were deleted too: a visit or a role of one that was deleted still says who it was."""
        return [trapper_to_record(t) for t in self._catalog().trappers(True)]

    def keep_trappers(self, trappers: list[dict]) -> None:
        self._catalog().save_trappers([trapper_from_record({**t, "id": t.get("id") or None}) for t in trappers])

    def roles(self, project: str, include_deleted: bool = False) -> list[dict]:
        return [{**{k: v for k, v in role_to_record(role).items() if k != "trapper_ref"}, "trapper": role.trapper, "research_project": project}
                for role in self._catalog().roles(project, include_deleted)]

    def keep_roles(self, project: str, roles: list[dict]) -> None:
        with _as_local_folder_error():
            self._catalog().save_roles(project, [Role(trapper=r.get("trapper"), role=r.get("role") or "contributor", audit=Audit(id=r.get("id")))
                                                 for r in roles])

    def checkpoint(self, project: str) -> Callable[[], None]:
        repository = self._repository()
        record, records = repository.read_project(project), repository.checkpoint(project)

        def put_back() -> None:
            if record is not None:
                repository.save_project(record)
            records()
        return put_back

    def project_record(self, project: str) -> dict | None:
        """The record of a research project as it is kept — removed or not —, or None."""
        found = self._repository().read_project(project)
        return project_to_record(found) if found is not None else None

    def put_project_record(self, record: dict) -> None:
        """Keeps the record of a research project as it is given — its id and dates too, as a backup has them —, in place of the one kept, or as a
        new one (with its folder)."""
        repository, project = self._repository(), project_from_record(record)
        if repository.read_project(project.acronym) is not None:
            repository.save_project(project)
        else:
            repository.add_project(project)

    def location_records(self, project: str) -> list[dict]:
        return [location_to_record(loc) for loc in self._repository().read_locations(project)]

    def put_location_records(self, project: str, records: list[dict]) -> None:
        self._repository().write_locations(project, [location_from_record(r, project) for r in records])

    def equipment_records(self, project: str, kind: str) -> list[dict]:
        return [equipment_to_record(i, kind) for i in self._repository().read_equipment(project, kind)]

    def put_equipment_records(self, project: str, kind: str, records: list[dict]) -> None:
        self._repository().write_equipment(project, kind, [equipment_from_record(r, kind, project) for r in records])


@contextmanager
def _as_local_folder_error():
    """The errors of the catalog as the callers of before catch them: a LocalFolderError, with the same words — some still read them."""
    try:
        yield
    except (UnknownProject, UnknownLocation, UnknownCamera) as exc:
        raise LocalFolderError(str(exc)) from exc
    except CatalogError as exc:
        raise LocalFolderError(exc.message) from exc
