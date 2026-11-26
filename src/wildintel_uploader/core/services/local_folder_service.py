"""Organizing a deployment into a local "collection" folder instead of
Trapper — the "Local folder" destination, for when there's no Trapper
account/instance involved at all.

A collection here is just a folder holding one subfolder per deployment,
with a small collection.json recording its own name (mirroring Trapper's
own Collection model, which needs nothing more than a name to create one).
Each deployment's own folder likewise gets a deployment.json with the
fields the wizard collected, since there's no Trapper database to register
them in."""
from __future__ import annotations

import csv
from contextlib import contextmanager
from dataclasses import replace
import json
import logging
from datetime import datetime
from pathlib import Path

from wildintel_uploader.core import identity, storage
from wildintel_uploader.core.storage import valid_project_id
from wildintel_uploader.core.services import audit, ids, visit_rules, visit_time

logger = logging.getLogger(__name__)

COLLECTION_METADATA_FILE = "collection.json"
DEPLOYMENT_METADATA_FILE = "deployment.json"
IMAGES_FILE = "images.json"
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


def check_collection(path: Path) -> dict:
    """Whether path already exists, and the collection name recorded in it
    from an earlier run, if any (None if it's missing, unreadable, or the
    folder is new/foreign)."""
    name = None
    metadata_path = path / COLLECTION_METADATA_FILE
    if metadata_path.is_file():
        try:
            name = json.loads(metadata_path.read_text(encoding="utf-8")).get("name")
        except (json.JSONDecodeError, OSError):
            name = None
    return {"exists": path.is_dir(), "name": name}


def write_collection_metadata(path: Path, name: str | None) -> None:
    """Creates the collection folder if it doesn't exist yet, and records
    its name — merged into whatever collection.json is already there, so
    reusing an existing collection never needs a name to keep the one it
    has."""
    path.mkdir(parents=True, exist_ok=True)
    metadata_path = path / COLLECTION_METADATA_FILE
    metadata: dict = {}
    if metadata_path.is_file():
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            metadata = {}
    if name:
        metadata["name"] = name
    metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")


def write_deployment_metadata(path: Path, deployment: dict) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / DEPLOYMENT_METADATA_FILE).write_text(
        json.dumps(deployment, indent=2, ensure_ascii=False), encoding="utf-8",
    )


def is_synced(deployment_dir: Path) -> bool:
    """Whether the deployment was synced from Trapper (its images.json says so): what Trapper holds is not modified here."""
    info = _read_json(deployment_dir / IMAGES_FILE)
    return isinstance(info, dict) and info.get("source") == "trapper"


def image_entry(name: str, local_time: str | None, source: str, extra: dict) -> dict:
    """One image of images.json: "name" and "local_time" (the camera's wall clock, None when unknown) are always there;
    "source" says where the rest comes from ("local" or "trapper") and "extra" holds those attributes, which are
    different for each source."""
    return {"name": name, "local_time": local_time, "source": source, "extra": extra}


def write_images_file(deployment_dir: Path, deployment_id: str, images: list[dict], *, source: str = "local") -> None:
    """images.json — what is known of each image of the deployment, for statistics and checks without opening the
    images again: {"deployment_id", "source", "image_count", "first", "last", "images": [...]}. "source" says where it
    comes from: "local" (the images were read here) or "trapper" (what Trapper holds for them); each image says it too.
    Build the images with image_entry. "first" and "last" are the
    earliest and latest "local_time" of the images (the camera's wall clock) that have one."""
    times = sorted(i["local_time"] for i in images if i.get("local_time"))
    summary = {"deployment_id": deployment_id, "source": source, "image_count": len(images), "first": times[0] if times else None, "last": times[-1] if times else None}
    (deployment_dir / IMAGES_FILE).write_text(json.dumps({**summary, "images": images}, indent=2, ensure_ascii=False), encoding="utf-8")


def list_deployments(collection_dir: Path) -> list[dict]:
    """Every deployment already organized in this collection folder — each
    subfolder holding a deployment.json (see write_deployment_metadata) —
    for the "use an existing deployment" branch of the "Local folder"
    destination. Empty if the folder doesn't exist."""
    if not collection_dir.is_dir():
        return []
    deployments = []
    for entry in sorted(collection_dir.iterdir()):
        if not entry.is_dir():
            continue
        metadata_path = entry / DEPLOYMENT_METADATA_FILE
        if not metadata_path.is_file():
            continue
        try:
            deployments.append(json.loads(metadata_path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue
    return deployments


# ── research projects and locations kept in the collections folder ──────────
#
#   <collections folder>/<research project id>/research_project.json
#   <collections folder>/<research project id>/locations.json
#   <collections folder>/<research project id>/<R0003>/<deployment id>/…
#
# The wizard's first question, "where was it taken?", is answered from these —
# or a new research project/location is added, by hand or from Trapper.

def project_dir(root: Path, research_project_id: str) -> Path:
    """The research project's own folder.

    Raises:
        LocalFolderError: the id can't be a folder name.
    """
    return root / storage.valid_project_id(research_project_id)


def imported_source_hashes(root: Path, research_project_id: str, exclude_deployment: str | None = None) -> dict[str, list[dict]]:
    """The images already imported into a research project's collections, by the SHA-1 of the original that was imported (what its
    preprocessing.json keeps as "source_hash") — each with {"deployment_id", "collection", "original"}. `exclude_deployment` leaves one
    deployment out (the one being imported again). Empty when the research project has no folder or nothing was preprocessed in it."""
    project = project_dir(root, research_project_id)
    found: dict[str, list[dict]] = {}
    if not project.is_dir():
        return found
    for log in sorted(project.glob("*/*/preprocessing.json")):
        deployment_id, collection = log.parent.name, log.parent.parent.name
        if exclude_deployment and deployment_id.lower() == exclude_deployment.lower():
            continue
        body = _read_json(log)
        for image in (body.get("images") if isinstance(body, dict) else None) or []:
            digest = image.get("source_hash") if isinstance(image, dict) else None
            if digest:
                found.setdefault(digest, []).append({"deployment_id": deployment_id, "collection": collection, "original": image.get("original")})
    return found


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


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


def _site_status_refusal(root: Path, research_project_id: str, locations: list[dict], location: dict, wanted: str) -> str | None:
    """Why the status of a site cannot be set by hand to `wanted` — None when it can. The visits say what is there: a camera that is out, and the visits still to be made."""
    site = str(location.get("location_id", ""))
    visits = list_visits(root, research_project_id)
    camera = visit_rules.camera_at_site(visits, site, "9999-12-31T23:59:59Z")
    if wanted == "active" and camera is None:
        return f"{site} is active when it has a camera: a visit puts it up (an Installation); the status cannot be set to active by hand."
    if wanted in ("ready", "planned", "archived") and camera is not None:
        return f"{site} has a camera out (put up in {camera.get('session')}): take it away with a visit — a Desinstallation, or a Stolen visit — before it is {wanted}."
    if wanted == "ready" and location.get("status") != "ready":
        return f"{site} is ready when a visit says Location start: its status cannot be set to ready by hand."
    if wanted in ("planned", "archived"):
        numbers = sorted({n for n in (visit_rules._session_number(v.get("session")) for v in visits) if n is not None})
        pending = [f"R{n:04d}" for n in numbers if any(str(s).lower() == site.lower() for s in visit_rules.revision_missing(n, visits, locations, "", list_unknown(root, research_project_id)))]
        if pending:
            return f"{site} still has a visit to be made in {', '.join(pending)}: it cannot be {wanted} until the revision is finished."
    return None


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


def _camera_status_refusal(camera: dict, wanted: str, visits: list[dict]) -> str | None:
    """Why the status of a camera cannot be set by hand to `wanted` — None when it can. A camera is active when a visit puts it up at a site (an Installation): it cannot be made so by
    hand, and it cannot leave the field — back to ready, to planned, or archived — while it is put up: a visit takes it away (a Desinstallation) or finds it stolen first."""
    name = str(camera.get("label") or camera.get("camera_id") or "")
    if wanted == "active":
        return f"The camera {name} is active when it is put up at a location: a visit does it (an Installation); its status cannot be set to active by hand."
    if wanted in ("ready", "planned", "archived"):
        for key in (camera.get("camera_id"), camera.get("label")):
            there = visit_rules.camera_at(visits, str(key), "9999-12-31T23:59:59Z") if key else None
            if there:
                return f"The camera {name} is put up at {there['site']} (since {there['date']}): take it away with a visit — a Desinstallation, or a Stolen visit — before it is {wanted}."
    return None


def _card_status_refusal(card: dict, wanted: str, visits: list[dict]) -> str | None:
    """Why the status of an SD card cannot be set by hand to `wanted` — None when it can. A card is active when a visit leaves it in a camera (an Installation, or a Revision that
    changes it): it cannot be made so by hand, and it cannot leave the field — back to ready, to planned, or archived — while it is in a camera: a visit collects it first."""
    name = str(card.get("label") or "")
    if wanted == "active":
        return f"The SD card {name} is active when it is in a camera: a visit leaves it there (an Installation, or a Revision); its status cannot be set to active by hand."
    if wanted in ("ready", "planned", "archived"):
        there = visit_rules.card_at(visits, name, "9999-12-31T23:59:59Z") if name else None
        if there:
            return f"The SD card {name} is in the camera at {there['site']} (since {there['date']}): collect it with a visit — a Revision, a Desinstallation, or a Stolen visit — before it is {wanted}."
    return None


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


def _raw_visits(root: Path, research_project_id: str) -> list[dict]:
    return _store(root).read_records(research_project_id, "visits")


def _write_raw_visits(root: Path, research_project_id: str, visits: list[dict]) -> None:
    _store(root).write_records(research_project_id, "visits", visits)


class _Refs:
    """What the visits of a research project point to, by id and by what it is called: its locations, cameras and SD cards, and the trappers — those that were deleted too."""

    def __init__(self, locations: list[dict], cameras: list[dict], sd_cards: list[dict], trappers: list[dict]):
        self.locations = locations
        self.by_label: dict[str, dict[str, dict]] = {"location": {}, "camera": {}, "sd": {}, "trapper": {}}
        self.by_id: dict[str, dict[str, dict]] = {"location": {}, "camera": {}, "sd": {}, "trapper": {}}
        for l in locations:
            self._add("location", l, [l.get("location_id")])
        for c in cameras:
            self._add("camera", c, [c.get("camera_id"), c.get("label")])
        for c in sd_cards:
            self._add("sd", c, [c.get("label")])
        for t in trappers:
            self._add("trapper", t, [t.get("name"), t.get("username")])

    def _add(self, kind: str, record: dict, labels: list) -> None:
        if record.get("id"):
            self.by_id[kind][record["id"]] = record
        for label in labels:
            if label:
                self.by_label[kind].setdefault(identity.key(kind, label), record)


# What a visit says of what it points to — (told as, kept as an id in, kind): told by what it is called, kept by the id. What cannot be found (a card nobody registered) is kept as it was said.
_POINTS_TO = (("location_id", "location_ref", "location"), ("camera_id", "camera_ref", "camera"), ("sd", "sd_ref", "sd"), ("setup_by", "setup_by_ref", "trapper"))
_CALLED = {
    "location": lambda r: r.get("location_id"), "camera": lambda r: r.get("label") or r.get("camera_id"), "sd": lambda r: r.get("label"), "trapper": lambda r: r.get("name"),
}


def camera_model_of(record: dict) -> str | None:
    """The model of a camera as Camtrap DP's cameraModel says it — the make and the model, make-model — from its record: the model alone when it has no make."""
    make, model = str(record.get("camera_make") or "").strip(), str(record.get("camera_model") or "").strip()
    return f"{make}-{model}" if make and model and not model.lower().startswith(make.lower()) else (model or None)


def _what_the_camera_is(record: dict) -> dict:
    """What a visit tells of its camera from its record (#231): it only points to it (camera_ref), and what the camera is — its model as Camtrap DP says it and
    its serial number — is the record's, copied for whoever needs it (the deployment), never kept in the visit."""
    out: dict = {}
    if (model := camera_model_of(record)) is not None:
        out["camera_model"] = model
    if str(record.get("camera_id") or "").strip():
        out["camera_serial"] = str(record["camera_id"]).strip()
    return out


def _refs(root: Path, research_project_id: str, trappers=None) -> _Refs:
    return _Refs(
        list_locations(root, research_project_id, include_deleted=True), list_field_items(root, research_project_id, "cameras", include_deleted=True),
        list_field_items(root, research_project_id, "sd_cards", include_deleted=True), _trapper_records(root, trappers),
    )


def _location_of(locations: list[dict], location_id) -> dict | None:
    return next((l for l in locations if str(l.get("location_id", "")).lower() == str(location_id or "").lower()), None)


def _site(visit: dict, refs: _Refs) -> str:
    """The site of a visit, as it is called — whether the visit is kept (by the id of its location) or told."""
    return str((refs.by_id["location"].get(visit.get("location_ref")) or {}).get("location_id") or visit.get("location_id") or "")


def _linked(visit: dict, refs: _Refs) -> dict:
    """A visit with what it points to said by id: the location, the camera, the SD card and who went and set it up are the ones the research project has — if it has them —, so the
    visit says *which* — their ids — and not what they are called, which can be corrected. What it points to that the research project has not is kept as it was said, and is
    linked when it has it."""
    out = dict(visit)
    for told, kept, kind in _POINTS_TO:
        if kind == "camera":
            _link_camera(out, refs)
            continue
        text = out.get(told)
        record = refs.by_label[kind].get(identity.key(kind, text)) if text not in (None, "") else None
        if record is not None and record.get("id"):
            out[kept] = record["id"]
            out.pop(told, None)
    names = [n.strip() for n in str(out.get("trappers") or "").split(",") if n.strip()]
    if names:
        found = [refs.by_label["trapper"].get(identity.key("trapper", n)) for n in names]
        known = [*(out.get("trapper_refs") or []), *[r["id"] for r in found if r is not None and r.get("id")]]
        if known:
            out["trapper_refs"] = list(dict.fromkeys(known))
        rest = [n for n, r in zip(names, found) if r is None or not r.get("id")]
        if rest:
            out["trappers"] = ", ".join(rest)
        else:
            out.pop("trappers", None)
    return out


def _link_camera(out: dict, refs: _Refs) -> None:
    """The camera of a visit kept by the id of its record (#231): the one it already points to (camera_ref), else the one it names — by its label, or by its
    serial number when it says only that. Then what the camera is (its model, its serial number) is the record's, and is not kept in the visit — unless the
    record says no model, when the one the visit wrote is kept. A camera with no record is kept as it was said, and is linked when it has one."""
    record = refs.by_id["camera"].get(out.get("camera_ref"))
    if record is None:
        text = out.get("camera_id") or out.get("camera_serial")
        record = refs.by_label["camera"].get(identity.key("camera", text)) if text not in (None, "") else None
    if record is None or not record.get("id"):
        out.pop("camera_ref", None)
        return
    out["camera_ref"] = record["id"]
    out.pop("camera_id", None)
    out.pop("camera_serial", None)
    if str(record.get("camera_model") or "").strip():
        out.pop("camera_model", None)


def _unlinked(visit: dict, refs: _Refs) -> dict:
    """A visit as it is told: what it points to said by what it is called now — and its camera with the id of its record beside (camera_ref) and what the record
    says it is (#231)."""
    out = dict(visit)
    for told, kept, kind in _POINTS_TO:
        record = refs.by_id[kind].get(out.get(kept) if kind == "camera" else out.pop(kept, None))
        if record is not None:
            out[told] = _CALLED[kind](record)
            if kind == "camera":
                out.update(_what_the_camera_is(record))
        elif kind == "camera":
            out.pop(kept, None)
    named = [str(refs.by_id["trapper"][t]["name"]) for t in out.pop("trapper_refs", None) or [] if t in refs.by_id["trapper"]]
    rest = [n.strip() for n in str(out.get("trappers") or "").split(",") if n.strip()]
    if named or "trappers" in out:
        out["trappers"] = ", ".join([*named, *rest]) or None
    return out


def _kept(visit: dict, refs: _Refs) -> dict:
    """A visit as it is kept: the instant, ISO 8601 in UTC with a Z (`when`), and not the day and the time of the wall clock of its location; and what it points to said by id."""
    visit = _two_fields(visit)
    if "status" in visit:   # kept before it was called camera_status
        visit = {("camera_status" if k == "status" else k): v for k, v in visit.items() if not (k == "status" and "camera_status" in visit)}
    if visit.get("when"):
        return _linked({k: v for k, v in visit.items() if k not in ("date", "time")}, refs)
    if not (visit.get("date") and visit.get("time")):
        return _linked(dict(visit), refs)  # no time to keep
    out = {k: v for k, v in visit.items() if k not in ("date", "time")}
    out["when"] = visit_time.to_when(visit["date"], visit["time"], _location_of(refs.locations, _site(visit, refs)))
    return _linked(out, refs)


def _two_fields(visit: dict) -> dict:
    """A visit kept with card_batteries_ok — one field for the batteries and the card — says each in a field of its own."""
    if "card_batteries_ok" not in visit:
        return visit
    battery, card = visit_rules.split_card_batteries(visit["card_batteries_ok"])
    out = {k: v for k, v in visit.items() if k != "card_batteries_ok"}
    if battery and not out.get("battery_status"):
        out["battery_status"] = battery
    if card and not out.get("card_status"):
        out["card_status"] = card
    return out


def _told(visit: dict, refs: _Refs) -> dict:
    """A visit as it is told: with the day and the time of the wall clock of its location, from its instant, beside it, and what it points to by what it is called. The card and
    the batteries are told as they are written now: a visit kept with SinPilas or CarFullSinPilas says NoBatteries or CarFullNoBatteries."""
    told = _unlinked(visit, refs)
    if not told.get("when"):
        return told
    date, time = visit_time.to_wall(told["when"], _location_of(refs.locations, told.get("location_id")))
    return {**told, "date": date, "time": time}


def _with_the_camera_there(visits: list[dict]) -> list[dict]:
    """The visits told with the camera they are of: a Revision, a Desinstallation or a Stolen visit does not say which camera — it is the one at its site, which the visit before says —,
    so it is told as that one (it is not kept: it would say twice what the visit that put it up says)."""
    out = [dict(v) for v in visits]
    there: dict[str, tuple[str, str | None]] = {}
    for v in sorted(out, key=visit_rules._stamp):
        site = str(v.get("location_id") or "").lower()
        if visit_rules.is_not_revised(v):
            continue
        actions = set(v.get("actions") or [])
        if not v.get("camera_id") and {"Revision", "Desinstallation", "Stolen"} & actions and "Installation" not in actions and site in there:
            v["camera_id"], model = there[site]
            if model and not v.get("camera_model"):
                v["camera_model"] = model
        if visit_rules._takes_away(v):
            there.pop(site, None)
        if visit_rules._leaves_camera(v) and v.get("camera_id"):
            there[site] = (v["camera_id"], v.get("camera_model"))
    return out


def list_visits(root: Path, research_project_id: str, location_id: str | None = None, trappers=None) -> list[dict]:
    """The visits kept for a research project, in the order they were registered — those to one location (found ignoring
    case) when it is given. Empty until one is registered.

    A visit is kept as an instant, `when` (ISO 8601, UTC, with a Z), and told with the day (`date`) and the time (`time`) of the wall clock of its
    location, in the timezone the location says. It is kept pointing to its location, its camera, its SD card and the trappers by their ids, and told with what they are called
    now (see ids). A file kept with a day and a time only, or with the names (an earlier version), is moved to instants and to ids when it is read — in the timezone its
    locations say —, and written back so; and the visits come the same.

    Raises:
        LocalFolderError: the research project id can't be a folder name.
    """
    raw = _raw_visits(root, research_project_id)
    refs = _refs(root, research_project_id, trappers)
    kept = []
    for visit in raw:
        try:
            one = _kept(visit, refs)
        except (KeyError, ValueError, TypeError):
            one = visit  # not a visit it can read the time of: left as it is
        if not one.get("id"):   # kept before the ids existed: the same one whenever it is read
            one = {**one, "id": ids.legacy_id("visit", f"{_site(one, refs)}|{one.get('when') or ''}", research_project_id)}
        kept.append(one)
    if kept != raw and raw:
        _write_raw_visits(root, research_project_id, kept)
    visits = _with_the_camera_there([_told(v, refs) for v in kept])
    if location_id is None:
        return visits
    return [v for v in visits if str(v.get("location_id", "")).lower() == location_id.lower()]


def require_research_project(root: Path, research_project_id: str) -> None:
    """Raises LocalFolderError when the research project isn't kept in the collections folder."""
    with _as_local_folder_error():
        _catalog(root).require_project(research_project_id)


def require_active_research_project(root: Path, research_project_id: str) -> None:
    """Raises LocalFolderError when the research project is not active: new visits are only kept to a project that is being worked on."""
    with _as_local_folder_error():
        _catalog(root).require_project(research_project_id, active=True)


def write_visit(root: Path, research_project_id: str, visit: dict) -> dict:
    """Registers a visit to a research project that's already kept here — given with the day and the time of the wall clock of its location,
    kept as an instant (see list_visits) and returned told.

    Raises:
        LocalFolderError: the research project isn't there.
    """
    write_visits(root, research_project_id, [visit])
    return _told(_raw_visits(root, research_project_id)[-1], _refs(root, research_project_id))


def list_unknown(root: Path, research_project_id: str) -> list[dict]:
    """The visits that are unknown — {"location_id", "session"}: the revisions before the first one kept to a site, of which nothing is known (see visit_rules.unknown_records)."""
    where = {l["id"]: l for l in list_locations(root, research_project_id, include_deleted=True) if l.get("id")}
    out = []
    for u in _store(root).read_records(research_project_id, "unknown_visits"):
        site = (where.get(u.get("location_ref")) or {}).get("location_id") or u.get("location_id")
        if site and u.get("session"):
            out.append({"location_id": site, "session": u["session"]})
    return out


def _write_unknown(root: Path, research_project_id: str, unknown: list[dict]) -> None:
    """Keeps the unknown visits — each pointing to its location by id, when the research project has it."""
    if not unknown:
        _store(root).delete_records(research_project_id, "unknown_visits")
        return
    where = {str(l.get("location_id", "")).lower(): l for l in list_locations(root, research_project_id, include_deleted=True)}
    stored = []
    for u in unknown:
        place = where.get(str(u["location_id"]).lower())
        stored.append({"location_ref": place["id"], "session": u["session"]} if place and place.get("id") else {"location_id": u["location_id"], "session": u["session"]})
    _store(root).write_records(research_project_id, "unknown_visits", stored)


def write_unknown(root: Path, research_project_id: str, new: list[dict]) -> int:
    """Keeps more unknown visits — those already kept are not repeated; returns how many were added.

    Raises:
        LocalFolderError: the research project isn't there."""
    _require_modifiable(root, research_project_id)
    require_research_project(root, research_project_id)
    have = list_unknown(root, research_project_id)
    keys = {(u["location_id"].lower(), u["session"].upper()) for u in have}
    added = [{"location_id": u["location_id"], "session": u["session"].upper()} for u in new if (u["location_id"].lower(), u["session"].upper()) not in keys]
    if added:
        _write_unknown(root, research_project_id, [*have, *added])
    return len(added)


def list_planned_revisions(root: Path, research_project_id: str) -> list[str]:
    """The revisions that were planned before any visit was made to them — "R0003": a revision is a trip to every location, and it exists in the visit book, with a planned
    visit to each location, from the day it is planned, not only from its first visit. Oldest first."""
    kept = {str(r.get("session") or "").upper() for r in _store(root).read_records(research_project_id, "planned_revisions") if r.get("session")}
    return sorted(kept)


def plan_revision(root: Path, research_project_id: str, session: str) -> str:
    """Keeps a revision as planned — `session` is "R0003" —, and says when it was.

    Raises:
        LocalFolderError: the research project isn't there or cannot be changed."""
    _require_modifiable(root, research_project_id)
    require_research_project(root, research_project_id)
    session = session.upper()
    if session not in list_planned_revisions(root, research_project_id):
        records = _store(root).read_records(research_project_id, "planned_revisions")
        _store(root).write_records(research_project_id, "planned_revisions", [*records, {"session": session, "created_at": audit.now()}])
    return session


def update_visit(root: Path, research_project_id: str, location_id: str, session: str, visit: dict) -> dict:
    """Replaces a visit kept — found by its site (ignoring case) and its revision, which is its key and does not change — with `visit`, given with the day and the
    time of the wall clock of its location; the deployment it closed, when it has one, stays. Returned told.

    Raises:
        LocalFolderError: the research project isn't there, or it has no visit to that site in that revision."""
    _require_modifiable(root, research_project_id)
    require_research_project(root, research_project_id)
    list_visits(root, research_project_id)  # an earlier file is moved to instants and to ids first
    refs = _refs(root, research_project_id)
    raw = _raw_visits(root, research_project_id)
    index = next((i for i, v in enumerate(raw) if _site(v, refs).lower() == location_id.lower() and str(v.get("session") or "").upper() == session.upper()), None)
    if index is None:
        raise LocalFolderError(f"There is no visit to {location_id} in {session}.")
    kept = _kept({**visit, "location_id": _site(raw[index], refs), "session": raw[index]["session"]}, refs)
    if raw[index].get("deployment_id"):
        kept["deployment_id"] = raw[index]["deployment_id"]
    raw[index] = audit.stamped(kept, raw[index])
    _write_raw_visits(root, research_project_id, raw)
    return _told(raw[index], refs)


def write_visits(root: Path, research_project_id: str, new: list[dict]) -> int:
    """Registers several visits at once to a research project that's already kept here; returns how many.

    Raises:
        LocalFolderError: the research project isn't there.
    """
    _require_modifiable(root, research_project_id)
    require_research_project(root, research_project_id)
    if new:
        list_visits(root, research_project_id)  # an earlier file is moved to instants and to ids first
        refs = _refs(root, research_project_id)
        at = audit.now()
        _write_raw_visits(root, research_project_id, _raw_visits(root, research_project_id) + [audit.stamped(_kept(v, refs), None, at) for v in new])
        # a visit that is known takes the place of the unknown one of its site in its revision
        known = {(str(v.get("location_id", "")).lower(), str(v.get("session") or "").upper()) for v in new}
        unknown = list_unknown(root, research_project_id)
        left = [u for u in unknown if (u["location_id"].lower(), u["session"].upper()) not in known]
        if len(left) != len(unknown):
            _write_unknown(root, research_project_id, left)
    return len(new)


def replace_visits(root: Path, research_project_id: str, visits: list[dict]) -> None:
    """Keeps these visits — told, as `list_visits` gives them — as all the research project's: a backup that is restored, say. Each is kept as an instant and pointing by id to
    what the research project has that it is called; it keeps its own `id` and its dates.

    Raises:
        LocalFolderError: the research project isn't there."""
    _require_modifiable(root, research_project_id)
    require_research_project(root, research_project_id)
    refs = _refs(root, research_project_id)
    _write_raw_visits(root, research_project_id, [_kept(v, refs) for v in visits])


def list_upload_failures(root: Path, research_project_id: str) -> list[dict]:
    """The uploads of the deployments of a research project that were tried and failed: {"deployment_id", "destination", "note", "at"}. An upload that was done is not here:
    it is told by the deployment's own folder — and a success takes the failure away."""
    return _store(root).read_records(research_project_id, "upload_failures")


def set_upload_failure(root: Path, research_project_id: str, deployment_id: str, destination: str, note: str | None) -> None:
    """Keeps that the upload of a deployment to a destination failed, with why — or, with no note (None), takes the failure away: it was tried again and worked.

    Raises:
        LocalFolderError: the research project isn't there."""
    require_research_project(root, research_project_id)
    failures = [f for f in list_upload_failures(root, research_project_id) if not (f.get("deployment_id") == deployment_id and f.get("destination") == destination)]
    if note is not None:
        failures.append({"deployment_id": deployment_id, "destination": destination, "note": note.strip() or None, "at": datetime.now().astimezone().isoformat(timespec="seconds")})
    _store(root).write_records(research_project_id, "upload_failures", failures)


def write_states(root: Path, research_project_id: str, states: dict[tuple[str, str], str | None]) -> int:
    """Keeps the `state` of the visits — found by their site (ignoring case) and their instant — where it changed; returns how many changed."""
    list_visits(root, research_project_id)  # an earlier file is moved to instants and to ids first
    refs = _refs(root, research_project_id)
    raw = _raw_visits(root, research_project_id)
    changed = 0
    for visit in raw:
        key = (_site(visit, refs).lower(), str(visit.get("when") or ""))
        if key in states and visit.get("state") != states[key]:
            visit["state"] = states[key]
            audit.touched(visit)
            changed += 1
    if changed:
        _write_raw_visits(root, research_project_id, raw)
    return changed


def closes_collection(visit: dict) -> bool:
    """Whether a visit closes a deployment: it collected the card — a Revision or a Desinstallation — and something was on it. Not an
    explicit 0 photos (nothing to timestamp), not an Installation (no card is taken), not a stolen camera, not a visit where nothing was
    collected (status 'Not revised')."""
    actions = visit.get("actions") or []
    if "Stolen" in actions or not {"Revision", "Desinstallation"} & set(actions):
        return False
    if str(visit.get("camera_status") or "").lower() in ("not revised", "no revisada", "no revisado"):
        return False
    photos = visit.get("num_photos")
    return photos is None or photos > 0


def closed_visits(root: Path, research_project_id: str) -> list[dict]:
    """The visits of a research project that left a camera (an Installation or a Revision) whose card a later visit has collected, and
    that have no deployment yet linked, newest first: {"visit", "end"} — the visit that left the camera and the next one at the same
    location, which collected the card (see closes_collection). The deployment is of the first: its card is the one that was collected.

    Raises:
        LocalFolderError: the research project id can't be a folder name.
    """
    by_location: dict[str, list[dict]] = {}
    for visit in list_visits(root, research_project_id):
        by_location.setdefault(str(visit.get("location_id", "")).lower(), []).append(visit)
    out = []
    for visits in by_location.values():
        visits.sort(key=lambda v: (str(v.get("date")), str(v.get("time"))))
        for start, end in zip(visits, visits[1:]):
            if start.get("deployment_id") or not closes_collection(end):
                continue
            if {"Installation", "Revision"} & set(start.get("actions") or []):
                out.append({"visit": start, "end": end})
    return sorted(out, key=lambda c: (str(c["visit"].get("date")), str(c["visit"].get("time"))), reverse=True)


def link_visit(root: Path, research_project_id: str, location_id: str, date: str, time: str, deployment_id: str) -> dict:
    """Records on a visit (found by its location, ignoring case, day and time) the deployment it closed.

    Raises:
        LocalFolderError: the visit isn't in the research project.
    """
    list_visits(root, research_project_id)  # an earlier file is moved to instants and to ids first
    raw = _raw_visits(root, research_project_id)
    refs = _refs(root, research_project_id)
    visit = next((v for v in raw if _site(v, refs).lower() == location_id.lower()
                  and (_told(v, refs).get("date"), _told(v, refs).get("time")) == (date, time)), None)
    if visit is None:
        raise LocalFolderError(f"There is no visit to {location_id} on {date} at {time} in {research_project_id}.")
    if visit.get("deployment_id") != deployment_id:
        visit["deployment_id"] = deployment_id
        audit.touched(visit)
    _write_raw_visits(root, research_project_id, raw)
    return _told(visit, refs)


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

TIMESTAMP_LOG_SUFFIX = "_FileTimestampLog.csv"
TIMESTAMP_LOG_FIELDS = ["Deployment", "StartDate", "StartTime", "EndDate", "EndTime"]


def timestamp_log_path(collection_dir: Path) -> Path:
    """<collection>/<collection>_FileTimestampLog.csv."""
    return collection_dir / f"{collection_dir.name}{TIMESTAMP_LOG_SUFFIX}"


def read_timestamp_log(path: Path) -> list[dict]:
    """The rows of a timestamp log — none if there isn't one yet.

    Raises:
        LocalFolderError: it exists but can't be read as one (no header, a column missing or repeated).
    """
    if not path.is_file():
        return []
    try:
        with path.open(newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            header = reader.fieldnames
            if not header:
                raise LocalFolderError(f"{path.name} has no header row.")
            repeated = sorted({name for name in header if header.count(name) > 1})
            if repeated:
                raise LocalFolderError(f"{path.name} repeats the columns: {', '.join(repeated)}.")
            missing = [name for name in TIMESTAMP_LOG_FIELDS if name not in header]
            if missing:
                raise LocalFolderError(f"{path.name} is missing the columns: {', '.join(missing)}.")
            rows = []
            for row in reader:
                clean = {name: (row.get(name) or "").strip() for name in TIMESTAMP_LOG_FIELDS}
                if clean["Deployment"]:
                    rows.append(clean)
            return rows
    except (OSError, UnicodeDecodeError, csv.Error) as exc:
        raise LocalFolderError(f"Could not read {path.name}: {exc}") from exc


# ── The collection's fieldwork log ──────────────────────────────────────────
#
# <collection>/<collection>_FieldworkLog.csv, beside the timestamp log: one row per deployment with its fields named as Camtrap DP
# names them, what the visits say of it (the sessions and the actions of the visit that left the camera and of the one that
# collected its card), the SD card and the photos counted on it. Times are UTC, with a Z. It is no longer written (#213): it is
# only read, when an older folder has it.

FIELDWORK_LOG_SUFFIX = "_FieldworkLog.csv"
FIELDWORK_LOG_FIELDS = [
    "deploymentID", "locationID", "deploymentStart", "deploymentEnd", "setupBy", "cameraID",
    "cameraModel", "cameraDelay", "cameraHeight", "cameraDepth", "cameraTilt", "cameraHeading", "detectionDistance",
    "timestampIssues", "baitUse", "featureType", "habitat", "deploymentGroups", "deploymentTags",
    "deploymentComments", "status", "collection", "cardSD", "photosCounted", "startSession", "startAction", "endSession", "endAction",
]


def fieldwork_log_path(collection_dir: Path) -> Path:
    """<collection>/<collection>_FieldworkLog.csv."""
    return collection_dir / f"{collection_dir.name}{FIELDWORK_LOG_SUFFIX}"


def read_fieldwork_log(path: Path) -> list[dict]:
    """The rows of a fieldwork log — none if there isn't one yet.

    Raises:
        LocalFolderError: it exists but can't be read as one (no header, or no deploymentID column).
    """
    if not path.is_file():
        return []
    try:
        with path.open(newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                raise LocalFolderError(f"{path.name} has no header row.")
            if "deploymentID" not in reader.fieldnames:
                raise LocalFolderError(f"{path.name} is missing the column: deploymentID.")
            return [{name: (row.get(name) or "").strip() for name in FIELDWORK_LOG_FIELDS} for row in reader if (row.get("deploymentID") or "").strip()]
    except (OSError, UnicodeDecodeError, csv.Error) as exc:
        raise LocalFolderError(f"Could not read {path.name}: {exc}") from exc
