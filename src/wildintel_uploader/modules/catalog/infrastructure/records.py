"""The catalog as records — the research projects, their locations, cameras, SD cards, people and roles as dicts, the shape they are kept in —,
for what still reads and writes them so (the visits, the backups, the sync): the contract CatalogRecords, over the catalog's use cases and its
repository."""
from __future__ import annotations

import logging
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import replace

from wildintel_uploader.modules.catalog.domain.models import Audit, CatalogError, Role, UnknownCamera, UnknownLocation, UnknownProject
from wildintel_uploader.modules.catalog.domain.ports import CatalogRecords, CatalogRepository, CatalogService
from wildintel_uploader.modules.catalog.infrastructure.mapping import (
    equipment_from_record, equipment_to_record, location_from_record, location_to_record, project_from_record, project_to_record, role_to_record,
    trapper_from_record, trapper_to_record,
)
from wildintel_uploader.shared import audit, storage
from wildintel_uploader.shared.storage import valid_project_id

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


class RecordsOf(CatalogRecords):
    """The catalog of a collections folder as records: its use cases (`catalog`) for what follows its rules, its repository for what is read and
    written as it is kept — a backup, a move to another storage —, which the use cases would date anew. The errors are told as the callers of
    before catch them (LocalFolderError, with the same words)."""

    def __init__(self, catalog: Callable[[], CatalogService], repository: Callable[[], CatalogRepository]) -> None:
        self._catalog, self._repository = catalog, repository

    # the research projects

    def research_projects(self, include_deleted: bool = False) -> list[dict]:
        return [project_to_record(p) for p in self._catalog().projects(include_deleted)]

    def has_project(self, project: str) -> bool:
        try:
            self._catalog().require_project(project)
        except UnknownProject:
            return False
        return True

    def add_project(self, record: dict) -> dict:
        with _as_local_folder_error():
            return project_to_record(self._catalog().add_project(project_from_record({k: v for k, v in record.items() if k not in audit.AUDIT_FIELDS and k != "id"})))

    def update_project(self, project: str, changes: dict) -> dict:
        with _as_local_folder_error():
            return project_to_record(self._catalog().update_project(project, {k: v for k, v in changes.items() if k not in audit.AUDIT_FIELDS}))

    def delete_project(self, project: str) -> dict:
        with _as_local_folder_error():
            self._catalog().delete_project(project)
        return {"deleted": project}

    def require_project(self, project: str, *, active: bool = False) -> None:
        with _as_local_folder_error():
            self._catalog().require_project(project, active=active)

    def require_modifiable(self, project: str) -> None:
        """Raises LocalFolderError when the research project is archived: an archived one can't be modified — nor its locations, cameras, SD cards,
        roles or visits — and never goes back."""
        if str((self.project_record(project) or {}).get("status") or "active") == "archived":
            raise LocalFolderError(f"The research project '{project}' is archived: it can't be modified.")

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

    # the locations

    def locations(self, project: str, include_deleted: bool = False) -> list[dict]:
        valid_project_id(project)
        return [location_to_record(loc) for loc in self._catalog().locations(project, include_deleted)]

    def add_location(self, project: str, location: dict, by_hand: bool = False) -> dict:
        with _as_local_folder_error():
            record = {k: v for k, v in location.items() if k not in audit.AUDIT_FIELDS and k != "id"}
            new = replace(location_from_record(record, project), audit=Audit())   # a new one: its id and dates are the catalog's to give
            return location_to_record(self._catalog().add_location(project, new, by_hand=by_hand))

    def change_location(self, project: str, location_id: str, changes: dict, by_visit: bool = False) -> dict:
        with _as_local_folder_error():
            return location_to_record(self._catalog().update_location(project, location_id, changes, by_visit=by_visit))

    def delete_location(self, project: str, location_id: str) -> dict:
        with _as_local_folder_error():
            location = self._catalog().location(project, location_id)
            self._catalog().delete_location(project, location_id)
        return {"deleted": location.location_id}

    def location_time(self, project: str, location_id: str | None) -> dict:
        valid_project_id(project)
        return self._catalog().location_time(project, location_id)

    def location_records(self, project: str) -> list[dict]:
        return [location_to_record(loc) for loc in self._repository().read_locations(project)]

    def put_location_records(self, project: str, records: list[dict]) -> None:
        self._repository().write_locations(project, [location_from_record(r, project) for r in records])

    # the cameras and the SD cards

    def equipment(self, project: str, kind: str, include_deleted: bool = False) -> list[dict]:
        valid_project_id(project)
        with _as_local_folder_error():
            return [{**equipment_to_record(i, kind), "research_project": project} for i in self._catalog().equipment(project, kind, include_deleted)]

    def all_equipment(self, kind: str) -> list[dict]:
        return [{**equipment_to_record(i, kind), "research_project": p} for p, i in self._catalog().all_equipment(kind)]

    def camera(self, project: str | None, key: str | None) -> dict | None:
        """The camera of a research project a deployment or a visit names: the one with that label, else the one with that serial number."""
        found = self._catalog().camera(project, key) if project and str(key or "").strip() else None
        return {**equipment_to_record(found, "cameras"), "research_project": project} if found is not None else None

    def set_camera_identity(self, project: str, label: str, make: str | None, model: str | None) -> dict:
        with _as_local_folder_error():
            camera = self._catalog().set_camera_identity(project, label, make, model)
        return {**equipment_to_record(camera, "cameras"), "research_project": project}

    def keep_equipment(self, project: str, kind: str, items: list[dict], by_hand: bool = False) -> None:
        with _as_local_folder_error():
            self._catalog().save_equipment(project, kind, [_equipment(i, kind, project) for i in items], by_hand=by_hand)

    def equipment_records(self, project: str, kind: str) -> list[dict]:
        return [equipment_to_record(i, kind) for i in self._repository().read_equipment(project, kind)]

    def put_equipment_records(self, project: str, kind: str, records: list[dict]) -> None:
        self._repository().write_equipment(project, kind, [equipment_from_record(r, kind, project) for r in records])

    # the people and their roles

    def trappers(self, include_deleted: bool = False) -> list[dict]:
        return [trapper_to_record(t) for t in self._catalog().trappers(include_deleted)]

    def trapper_records(self) -> list[dict]:
        """The trappers, those that were deleted too: a visit or a role of one that was deleted still says who it was."""
        return self.trappers(include_deleted=True)

    def keep_trappers(self, trappers: list[dict]) -> None:
        self._catalog().save_trappers([trapper_from_record({**t, "id": t.get("id") or None}) for t in trappers])

    def roles(self, project: str, include_deleted: bool = False) -> list[dict]:
        out = []
        for role in self._catalog().roles(project, include_deleted):
            record = {k: v for k, v in role_to_record(role).items() if k != "trapper_ref"}
            out.append({**record, "trapper": role.trapper, "research_project": project})
        return out

    def keep_roles(self, project: str, roles: list[dict]) -> None:
        with _as_local_folder_error():
            self._catalog().save_roles(project, [Role(trapper=r.get("trapper"), role=r.get("role") or "contributor", audit=Audit(id=r.get("id"))) for r in roles])


@contextmanager
def _as_local_folder_error():
    """The errors of the catalog as the callers of before catch them: a LocalFolderError, with the same words — some still read them."""
    try:
        yield
    except (UnknownProject, UnknownLocation, UnknownCamera) as exc:
        raise LocalFolderError(str(exc)) from exc
    except CatalogError as exc:
        raise LocalFolderError(exc.message) from exc


def _equipment(record: dict, kind: str, research_project_id: str):
    """A camera or an SD card as a caller of before gives it: with the id it says — none for a new one, which the catalog gives."""
    item = equipment_from_record(record, kind, research_project_id)
    return item if record.get("id") else replace(item, audit=Audit())
