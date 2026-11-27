"""The catalog as records — the research projects, their locations, cameras, SD cards, people and roles as dicts, the shape they are kept in —,
for what still reads and writes them so (the visits, the backups, the sync): each function asks the catalog's use cases or its repository, and
tells its errors as the code of before caught them (LocalFolderError, with the same words). Moved from local_folder_service (#248)."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
import logging
from pathlib import Path

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

# What is kept of the research projects — the projects, their locations, visits, cameras and SD cards — goes through `storage` (see core/storage): the JSON files of the
# collections folder today, whatever backend is registered tomorrow. This module has the rules; the store only keeps. What is not a record — the images, and what is
# written beside them — stays a file of the collections folder.
LocalFolderError = storage.StorageError   # a research project or location can't be read or saved in the collections folder


def _store(root: Path) -> storage.ProjectStore:
    return storage.open_store(root)


# ── research projects and locations kept in the collections folder ──────────
#
#   <collections folder>/<research project id>/research_project.json
#   <collections folder>/<research project id>/locations.json
#   <collections folder>/<research project id>/<R0003>/<deployment id>/…
#
# The wizard's first question, "where was it taken?", is answered from these —
# or a new research project/location is added, by hand or from Trapper.

def list_research_projects(root: Path, include_deleted: bool = False) -> list[dict]:
    """Every research project kept in the collections folder — empty if there is none yet. A removed one is kept, but is not listed (`include_deleted`
    lists it too). The catalog's (modules.catalog): see CatalogService.projects."""
    from wildintel_uploader.modules.catalog.infrastructure.mapping import project_to_record
    return [project_to_record(p) for p in _catalog(root).projects(include_deleted)]


def has_research_project(root: Path, research_project_id: str) -> bool:
    """Whether the research project is kept in the collections folder — and was not removed.

    Raises:
        LocalFolderError: the research project id can't be a folder name.
    """
    from wildintel_uploader.modules.catalog.domain.models import UnknownProject
    try:
        _catalog(root).require_project(research_project_id)
    except UnknownProject:
        return False
    return True


def write_research_project(root: Path, project: dict) -> dict:
    """Adds a research project and its folder, by the rules of the catalog (CatalogService.add_project): one removed comes back, with its own creation.

    Raises:
        LocalFolderError: the acronym can't be a folder name, or it's already there.
    """
    from wildintel_uploader.modules.catalog.infrastructure.mapping import project_from_record, project_to_record
    with _as_local_folder_error():
        return project_to_record(_catalog(root).add_project(project_from_record({k: v for k, v in project.items() if k not in audit.AUDIT_FIELDS and k != "id"})))


def _project_status(root: Path, research_project_id: str) -> str:
    project = project_record(root, research_project_id)
    return str((project or {}).get("status") or "active")


def _require_modifiable(root: Path, research_project_id: str) -> None:
    """Raises LocalFolderError when the research project is archived: an archived one can't be modified — nor its locations, cameras, SD cards, roles or visits — and never goes back."""
    if _project_status(root, research_project_id) == "archived":
        raise LocalFolderError(f"The research project '{research_project_id}' is archived: it can't be modified.")


def update_research_project(root: Path, research_project_id: str, changes: dict) -> dict:
    """Changes a kept research project's fields — only the keys in changes, the rest stay; never its acronym. CatalogService.update_project.

    Raises:
        LocalFolderError: the research project isn't there, it is archived, or it has visits and would go back to planned.
    """
    from wildintel_uploader.modules.catalog.infrastructure.mapping import project_to_record
    with _as_local_folder_error():
        return project_to_record(_catalog(root).update_project(research_project_id, {k: v for k, v in changes.items() if k not in audit.AUDIT_FIELDS}))


def delete_research_project(root: Path, research_project_id: str) -> dict:
    """Removes a research project — logically —, unless it holds collections, deployments or images. CatalogService.delete_project.

    Raises:
        LocalFolderError: the research project isn't there, it is archived, or it holds more than its own records.
    """
    with _as_local_folder_error():
        _catalog(root).delete_project(research_project_id)
    return {"deleted": research_project_id}


def list_locations(root: Path, research_project_id: str, include_deleted: bool = False) -> list[dict]:
    """The locations kept for a research project — empty until one is added. A removed one is kept, but is not listed (`include_deleted` lists it
    too: the visits made there still say their time in its timezone). The catalog's: see CatalogService.locations.

    Raises:
        LocalFolderError: the research project id can't be a folder name.
    """
    from wildintel_uploader.modules.catalog.infrastructure.mapping import location_to_record
    valid_project_id(research_project_id)
    return [location_to_record(loc) for loc in _catalog(root).locations(research_project_id, include_deleted)]




def write_location(root: Path, research_project_id: str, location: dict, by_hand: bool = False) -> dict:
    """Adds a location to a research project that's already kept here — CatalogService.add_location.

    Raises:
        LocalFolderError: the research project isn't there or is archived, the location id is already used in it, or — by hand — it would not start
            pending or planned.
    """
    from wildintel_uploader.modules.catalog.domain.models import Audit
    from wildintel_uploader.modules.catalog.infrastructure.mapping import location_from_record, location_to_record
    with _as_local_folder_error():
        record = {k: v for k, v in location.items() if k not in audit.AUDIT_FIELDS and k != "id"}
        new = replace(location_from_record(record, research_project_id), audit=Audit())   # a new one: its id and dates are the catalog's to give
        return location_to_record(_catalog(root).add_location(research_project_id, new, by_hand=by_hand))


def update_location(root: Path, research_project_id: str, location_id: str, changes: dict, by_visit: bool = False) -> dict:
    """Changes a kept location's fields — CatalogService.update_location: its timezone and summer-time setting are fixed, an archived one stays
    archived, and by hand its status changes only where the visits allow.

    Raises:
        LocalFolderError: the research project is archived, the location isn't there, or what is asked can't be.
    """
    from wildintel_uploader.modules.catalog.infrastructure.mapping import location_to_record
    with _as_local_folder_error():
        return location_to_record(_catalog(root).update_location(research_project_id, location_id, changes, by_visit=by_visit))


def delete_location(root: Path, research_project_id: str, location_id: str) -> dict:
    """Removes a location — logically — unless it comes from TRAPPER or visits were made to it: CatalogService.delete_location.

    Raises:
        LocalFolderError: the location isn't there, it comes from Trapper, or visits were made to it.
    """
    with _as_local_folder_error():
        location = _catalog(root).location(research_project_id, location_id)
        _catalog(root).delete_location(research_project_id, location_id)
    return {"deleted": location.location_id}


# ── The cameras and the SD cards of a research project ──────────────────────────────────────────────────────────
#
# <research project>/cameras.json and <research project>/sd_cards.json, beside its locations and its visits: they belong to the research project and travel
# with its collections. (The trappers are people, not things of a project: they stay in the settings.)

def list_field_items(root: Path, research_project_id: str, kind: str, include_deleted: bool = False) -> list[dict]:
    """The cameras (`kind` "cameras") or the SD cards ("sd_cards") of a research project — each with its `research_project` set to it. A removed one
    is kept, but is not listed (`include_deleted` lists it too). The catalog's: CatalogService.equipment."""
    from wildintel_uploader.modules.catalog.infrastructure.mapping import equipment_to_record
    valid_project_id(research_project_id)
    with _as_local_folder_error():
        return [{**equipment_to_record(i, kind), "research_project": research_project_id} for i in _catalog(root).equipment(research_project_id, kind, include_deleted)]


def camera_record(root: Path, research_project_id: str | None, key: str | None) -> dict | None:
    """The camera of a research project a deployment or a visit names (`key`): the one with that label, else the one with that serial number — case
    aside. None when it names none, or the research project has none. CatalogService.camera."""
    from wildintel_uploader.modules.catalog.infrastructure.mapping import equipment_to_record
    camera = _catalog(root).camera(research_project_id, key) if research_project_id and str(key or "").strip() else None
    return {**equipment_to_record(camera, "cameras"), "research_project": research_project_id} if camera is not None else None


def set_camera_identity(root: Path, research_project_id: str, label: str, make: str | None, model: str | None) -> dict:
    """Keeps the make and the model a camera writes in its images in its record. Returns the record. CatalogService.set_camera_identity."""
    from wildintel_uploader.modules.catalog.infrastructure.mapping import equipment_to_record
    with _as_local_folder_error():
        camera = _catalog(root).set_camera_identity(research_project_id, label, make, model)
    return {**equipment_to_record(camera, "cameras"), "research_project": research_project_id}


def write_field_items(root: Path, research_project_id: str, kind: str, items: list[dict], by_hand: bool = False) -> None:
    """Keeps these cameras or SD cards as the research project's — the whole list: what was kept and is not in it is removed logically. By hand, the
    status changes only where the visits allow. CatalogService.save_equipment.

    Raises:
        LocalFolderError: the research project isn't in the collections folder or is archived, or the status is changed where the visits do not allow it.
    """
    with _as_local_folder_error():
        _catalog(root).save_equipment(research_project_id, kind, [_equipment(i, kind, research_project_id) for i in items], by_hand=by_hand)


def _equipment(record: dict, kind: str, research_project_id: str):
    """A camera or an SD card as a caller of before gives it: with the id it says — none for a new one, which the catalog gives."""
    from wildintel_uploader.modules.catalog.domain.models import Audit
    from wildintel_uploader.modules.catalog.infrastructure.mapping import equipment_from_record
    item = equipment_from_record(record, kind, research_project_id)
    return item if record.get("id") else replace(item, audit=Audit())


# ── The roles of a research project ─────────────────────────────────────────────────────────────────────────────
#
# What each trapper is in a research project — a contributor's role in Camtrap DP —: <research project>/roles.json. The trappers, the people, are global (the settings);
# their roles are the project's.

# ── The trappers ────────────────────────────────────────────────────────────────────────────────────────────────
#
# The people who go to the field are the same whatever the research project: they belong to none, and are kept beside them (the store's global records). What each is in a
# project is its role, which is the project's.

@contextmanager
def _as_local_folder_error():
    """The errors of the catalog as the callers of before catch them: a LocalFolderError, with the same words — some still read them."""
    from wildintel_uploader.modules.catalog.domain.models import CatalogError, UnknownCamera, UnknownLocation, UnknownProject
    try:
        yield
    except (UnknownProject, UnknownLocation, UnknownCamera) as exc:
        raise LocalFolderError(str(exc)) from exc
    except CatalogError as exc:
        raise LocalFolderError(exc.message) from exc


def _catalog(root: Path):
    """The catalog kept in this collections folder (modules.catalog, #248), put together as the entry points put it (entrypoints.wiring)."""
    from wildintel_uploader.entrypoints import wiring   # here: wiring puts together modules that import this one
    return wiring.build_catalog(root, wiring.build_settings())


def _catalog_repository(root: Path):
    """Where the catalog of this collections folder is kept, as the settings say (DATA.catalog_storage): what is read and written as it is kept —
    a backup, a move to another storage — goes there, not through the use cases, which would date it anew."""
    from wildintel_uploader.entrypoints import wiring
    return wiring.catalog_repository(root, wiring.build_settings())


def project_record(root: Path, research_project_id: str) -> dict | None:
    """The record of a research project as it is kept — removed or not —, or None: wherever the catalog is kept."""
    from wildintel_uploader.modules.catalog.infrastructure.mapping import project_to_record
    project = _catalog_repository(root).read_project(research_project_id)
    return project_to_record(project) if project is not None else None


def put_project_record(root: Path, record: dict) -> None:
    """Keeps the record of a research project as it is given — its id and dates too, as a backup has them —, in place of the one kept, or as a new
    one (with its folder): wherever the catalog is kept."""
    from wildintel_uploader.modules.catalog.infrastructure.mapping import project_from_record
    repository, project = _catalog_repository(root), project_from_record(record)
    if repository.read_project(project.acronym) is not None:
        repository.save_project(project)
    else:
        repository.add_project(project)


def equipment_records(root: Path, research_project_id: str, kind: str) -> list[dict]:
    """The cameras or the SD cards of a research project as they are kept — the removed ones too —: wherever the catalog is kept."""
    from wildintel_uploader.modules.catalog.infrastructure.mapping import equipment_to_record
    return [equipment_to_record(i, kind) for i in _catalog_repository(root).read_equipment(research_project_id, kind)]


def put_equipment_records(root: Path, research_project_id: str, kind: str, records: list[dict]) -> None:
    """Keeps these as all the cameras or SD cards of a research project, as they are given — their ids and dates too, as a backup has them."""
    from wildintel_uploader.modules.catalog.infrastructure.mapping import equipment_from_record
    _catalog_repository(root).write_equipment(research_project_id, kind, [equipment_from_record(r, kind, research_project_id) for r in records])


def location_records(root: Path, research_project_id: str) -> list[dict]:
    """The locations of a research project as they are kept — the removed ones too —: wherever the catalog is kept."""
    from wildintel_uploader.modules.catalog.infrastructure.mapping import location_to_record
    return [location_to_record(loc) for loc in _catalog_repository(root).read_locations(research_project_id)]


def put_location_records(root: Path, research_project_id: str, records: list[dict]) -> None:
    """Keeps these as all the locations of a research project, as they are given — their ids and dates too, as a backup has them."""
    from wildintel_uploader.modules.catalog.infrastructure.mapping import location_from_record
    _catalog_repository(root).write_locations(research_project_id, [location_from_record(r, research_project_id) for r in records])


def list_trappers(root: Path, include_deleted: bool = False) -> list[dict]:
    """The trappers — the people, whatever the research project —, as records. One that was deleted is kept, but is not listed (`include_deleted`
    lists it too: the visits it made still say who it was). The catalog's (modules.catalog): see CatalogService.trappers."""
    from wildintel_uploader.modules.catalog.infrastructure.mapping import trapper_to_record
    return [trapper_to_record(t) for t in _catalog(root).trappers(include_deleted)]


def write_trappers(root: Path, trappers: list[dict]) -> None:
    """Keeps these trappers as all of them, by the rules of the catalog (modules.catalog.domain.rules.saved_trappers): one is the one kept when it says
    its `id`, or its username; an archived one is kept as it was; one no longer listed is deleted logically, and one listed again comes back."""
    from wildintel_uploader.modules.catalog.infrastructure.mapping import trapper_from_record
    _catalog(root).save_trappers([trapper_from_record({**t, "id": t.get("id") or None}) for t in trappers])


def _trapper_records(root: Path, trappers=None) -> list[dict]:
    """The trappers as records, those that were deleted too: a visit or a role of one that was deleted still says who it was. `trappers` are those to use instead of the kept ones
    (the settings that are being saved)."""
    if trappers is None:
        return list_trappers(root, include_deleted=True)
    return [t if isinstance(t, dict) else t.model_dump(mode="json") for t in trappers]


def list_roles(root: Path, research_project_id: str, include_deleted: bool = False, trappers=None) -> list[dict]:
    """The roles of a research project — each with its `research_project` and the name its trapper has now. A removed one is kept, but is not listed.
    CatalogService.roles."""
    from wildintel_uploader.modules.catalog.infrastructure.mapping import role_to_record
    out = []
    for role in _catalog(root).roles(research_project_id, include_deleted):
        record = {k: v for k, v in role_to_record(role).items() if k != "trapper_ref"}
        out.append({**record, "trapper": role.trapper, "research_project": research_project_id})
    return out


def write_roles(root: Path, research_project_id: str, roles: list[dict], trappers=None) -> None:
    """Keeps these roles — each with the name of its trapper — as all of the research project's, each by the id of its trapper. CatalogService.save_roles.

    Raises:
        LocalFolderError: the research project isn't in the collections folder.
    """
    from wildintel_uploader.modules.catalog.domain.models import Audit, Role
    with _as_local_folder_error():
        _catalog(root).save_roles(research_project_id, [Role(trapper=r.get("trapper"), role=r.get("role") or "contributor",
                                                             audit=Audit(id=r.get("id"))) for r in roles])


def list_all_field_items(root: Path, kind: str) -> list[dict]:
    """The cameras or the SD cards of every research project kept in the collections folder, project after project."""
    from wildintel_uploader.modules.catalog.infrastructure.mapping import equipment_to_record
    return [{**equipment_to_record(i, kind), "research_project": p} for p, i in _catalog(root).all_equipment(kind)]


def list_all_roles(root: Path, trappers=None) -> list[dict]:
    """The roles of every research project kept in the collections folder, project after project."""
    return [role for project in list_research_projects(root) for role in list_roles(root, project["acronym"])]


def require_research_project(root: Path, research_project_id: str) -> None:
    """Raises LocalFolderError when the research project isn't kept in the collections folder."""
    with _as_local_folder_error():
        _catalog(root).require_project(research_project_id)




def require_active_research_project(root: Path, research_project_id: str) -> None:
    """Raises LocalFolderError when the research project is not active: new visits are only kept to a project that is being worked on."""
    with _as_local_folder_error():
        _catalog(root).require_project(research_project_id, active=True)




def location_time(root: Path, research_project_id: str, location_id: str | None) -> dict:
    """The timezone and summer-time setting kept for a location (found ignoring case) — only the ones it has: CatalogService.location_time.

    Raises:
        LocalFolderError: the research project id can't be a folder name.
    """
    valid_project_id(research_project_id)
    return _catalog(root).location_time(research_project_id, location_id)


def location_time_in(project_folder: Path, location_id: str | None) -> dict:
    """location_time for a research project's folder, wherever it is: the folder is named by the research project, and the collections folder is the
    one that holds it. Empty when its name can't be a research project's."""
    try:
        valid_project_id(project_folder.name)
    except LocalFolderError:
        return {}
    return _catalog(project_folder.parent).location_time(project_folder.name, location_id)


# ── the collection's timestamp log ──────────────────────────────────────────
#
#   <collection folder>/<collection>_FileTimestampLog.csv — as wildintel-tools has it
#
#   Deployment,StartDate,StartTime,EndDate,EndTime
#   r0003-dona_0007_b,2024:09:04,13:10:00,2024:11:04,14:28:00
#
# One row per deployment, named in lower case as Trapper keeps its ids: when its images were taken, as the camera's local
# wall-clock time. wildintel-tools' check-deployments reads it. It is no longer written (#213): it is only read, when an older
# folder or one made with wildintel-tools has it.

# ── The collection's fieldwork log ──────────────────────────────────────────
#
# <collection>/<collection>_FieldworkLog.csv, beside the timestamp log: one row per deployment with its fields named as Camtrap DP
# names them, what the visits say of it (the sessions and the actions of the visit that left the camera and of the one that
# collected its card), the SD card and the photos counted on it. Times are UTC, with a Z. It is no longer written (#213): it is
# only read, when an older folder has it.

