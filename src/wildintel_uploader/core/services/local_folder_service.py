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
import json
import logging
import re
from datetime import datetime
from pathlib import Path

from wildintel_uploader.core import storage
from wildintel_uploader.core.config import migrate_gear
from wildintel_uploader.core.services import audit, visit_time

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


def list_research_projects(root: Path) -> list[dict]:
    """Every research project already kept in the collections folder. Empty if there is none yet (the first run)."""
    return _store(root).list_projects()


def has_research_project(root: Path, research_project_id: str) -> bool:
    """Whether the research project is kept in the collections folder.

    Raises:
        LocalFolderError: the research project id can't be a folder name.
    """
    return _store(root).has_project(research_project_id)


def write_research_project(root: Path, project: dict) -> dict:
    """Adds a research project: its folder (named by its acronym) and its record.

    Raises:
        LocalFolderError: the acronym can't be a folder name, or it's already there.
    """
    _store(root).add_project(project)
    project_dir(root, project["acronym"]).mkdir(parents=True, exist_ok=True)   # its folder, where its collections will go
    return project


def update_research_project(root: Path, research_project_id: str, changes: dict) -> dict:
    """Changes a kept research project's fields — only the keys in changes, the rest stay. The acronym names its folder, so it is not one of them.

    Raises:
        LocalFolderError: the research project isn't there.
    """
    store = _store(root)
    project = store.get_project(research_project_id)
    if project is None:
        raise LocalFolderError(f"The research project '{research_project_id}' isn't in the collections folder.")
    project = {**project, **{k: v for k, v in changes.items() if k != "acronym"}}
    store.save_project(research_project_id, project)
    return project


def delete_research_project(root: Path, research_project_id: str) -> dict:
    """Removes a research project with its locations and its visits. Only what the app keeps of the project itself goes: a project that holds
    anything else (a collection, a deployment, images) is not touched, as it would take the work with it.

    Raises:
        LocalFolderError: the research project isn't there, or it holds more than its own files.
    """
    store = _store(root)
    folder = project_dir(root, research_project_id)
    if not store.has_project(research_project_id):
        raise LocalFolderError(f"The research project '{research_project_id}' isn't in the collections folder.")
    own = store.owned_names(research_project_id)
    others = sorted(e.name for e in folder.iterdir() if e.name not in own) if folder.is_dir() else []
    if others:
        raise LocalFolderError(
            f"The research project '{research_project_id}' still holds {', '.join(others[:5])}{' and more' if len(others) > 5 else ''}: "
            "it can't be deleted until those are removed (they hold collections, deployments or images)."
        )
    store.delete_project(research_project_id)
    if folder.is_dir():
        folder.rmdir()
    return {"deleted": research_project_id}


def list_locations(root: Path, research_project_id: str) -> list[dict]:
    """The locations kept for a research project — empty until one is added.

    Raises:
        LocalFolderError: the research project id can't be a folder name.
    """
    # what was kept as "retired" is archived now
    return [{**l, "status": "archived"} if l.get("status") == "retired" else l for l in _store(root).read_records(research_project_id, "locations")]


def write_location(root: Path, research_project_id: str, location: dict) -> dict:
    """Adds a location to a research project that's already kept here.

    Raises:
        LocalFolderError: the research project isn't there, or the location
            id is already used in it.
    """
    require_research_project(root, research_project_id)
    locations = list_locations(root, research_project_id)
    if any(l.get("location_id", "").lower() == location["location_id"].lower() for l in locations):
        raise LocalFolderError(f"The location '{location['location_id']}' already exists in {research_project_id}.")
    # the day it was put into production is the day it was created, when it is not said
    location = {**location, "in_service": location.get("in_service") or datetime.now().date().isoformat()}
    locations.append(location)
    _store(root).write_records(research_project_id, "locations", locations)
    return location


def update_location(root: Path, research_project_id: str, location_id: str, changes: dict) -> dict:
    """Changes a kept location's fields (found ignoring case) — only the keys in changes, the rest stay. Its timezone, and whether its cameras ignore
    summer time, are fixed when it is created: every instant kept for it (a visit's `when`) was worked out with them, so they say the same or are refused.

    An archived location is archived for good: it never goes back to active or to planned.

    Raises:
        LocalFolderError: the research project or the location isn't there, the timezone (or the summer-time setting) is changed, or an archived location is given another status.
    """
    locations = list_locations(root, research_project_id)
    index = next((i for i, l in enumerate(locations) if l.get("location_id", "").lower() == location_id.lower()), None)
    if index is None:
        raise LocalFolderError(f"The location '{location_id}' isn't in {research_project_id}.")
    if locations[index].get("status") == "archived" and changes.get("status", "archived") != "archived":
        raise LocalFolderError(f"The status of a location can't be changed once it is archived: {location_id} is archived for good.")
    now = {"timezone": locations[index].get("timezone") or visit_time.DEFAULT_TIMEZONE, "ignore_dst": bool(locations[index].get("ignore_dst"))}
    for key, label in (("timezone", "timezone"), ("ignore_dst", "summer-time setting")):
        if key in changes:
            wanted = (changes[key] or visit_time.DEFAULT_TIMEZONE) if key == "timezone" else bool(changes[key])
            if wanted != now[key]:
                raise LocalFolderError(f"The {label} of a location can't be changed once it is created: {location_id} is {now[key]}.")
            changes = {k: v for k, v in changes.items() if k != key}
    locations[index] = {**locations[index], **changes}
    _store(root).write_records(research_project_id, "locations", locations)
    return locations[index]


def delete_location(root: Path, research_project_id: str, location_id: str) -> dict:
    """Removes a kept location (found ignoring case). One that holds visits stays, as they would be left with no place; so does one taken from
    Trapper, which is only read here — mark a location as archived instead and it is no longer offered.

    Raises:
        LocalFolderError: the location isn't there, it comes from Trapper, or visits were made to it.
    """
    locations = list_locations(root, research_project_id)
    index = next((i for i, l in enumerate(locations) if l.get("location_id", "").lower() == location_id.lower()), None)
    if index is None:
        raise LocalFolderError(f"The location '{location_id}' isn't in {research_project_id}.")
    if locations[index].get("trapper_pk") is not None:
        raise LocalFolderError(f"The location '{location_id}' comes from Trapper, so it can't be deleted here.")
    visits = len(list_visits(root, research_project_id, location_id))
    if visits:
        raise LocalFolderError(f"The location '{location_id}' still has {visits} visit{'s' if visits != 1 else ''}: it can't be deleted — mark it as archived instead.")
    removed = locations.pop(index)
    _store(root).write_records(research_project_id, "locations", locations)
    return {"deleted": removed["location_id"]}


# ── The cameras and the SD cards of a research project ──────────────────────────────────────────────────────────
#
# <research project>/cameras.json and <research project>/sd_cards.json, beside its locations and its visits: they belong to the research project and travel
# with its collections. (The trappers are people, not things of a project: they stay in the settings.)

def list_field_items(root: Path, research_project_id: str, kind: str) -> list[dict]:
    """The cameras (`kind` "cameras") or the SD cards ("sd_cards") kept for a research project — each with its `research_project` set to it. Empty until one is kept."""
    return [{**migrate_gear(i), "research_project": research_project_id} for i in _store(root).read_records(research_project_id, kind)]


def write_field_items(root: Path, research_project_id: str, kind: str, items: list[dict]) -> None:
    """Keeps these cameras or SD cards as the research project's — the whole list, replacing what was kept.

    Raises:
        LocalFolderError: the research project isn't in the collections folder.
    """
    require_research_project(root, research_project_id)
    store = _store(root)
    # each one keeps its `created_at`, and gets a new `updated_at` when it changed — what the page sends for them is not taken (see audit)
    before = {str(i.get("label") or "").strip().lower(): i for i in store.read_records(research_project_id, kind)}
    at = audit.now()
    store.write_records(research_project_id, kind, [
        audit.stamped({k: v for k, v in item.items() if k != "research_project"}, before.get(str(item.get("label") or "").strip().lower()), at) for item in items
    ])


def list_all_field_items(root: Path, kind: str) -> list[dict]:
    """The cameras or the SD cards of every research project kept in the collections folder, project after project."""
    return [item for project in list_research_projects(root) for item in list_field_items(root, project["acronym"], kind)]


def _raw_visits(root: Path, research_project_id: str) -> list[dict]:
    return _store(root).read_records(research_project_id, "visits")


def _write_raw_visits(root: Path, research_project_id: str, visits: list[dict]) -> None:
    _store(root).write_records(research_project_id, "visits", visits)


def _location_of(locations: list[dict], location_id) -> dict | None:
    return next((l for l in locations if str(l.get("location_id", "")).lower() == str(location_id or "").lower()), None)


def _kept(visit: dict, locations: list[dict]) -> dict:
    """A visit as it is kept: the instant, ISO 8601 in UTC with a Z (`when`), and not the day and the time of the wall clock of its location."""
    if visit.get("when"):
        return {k: v for k, v in visit.items() if k not in ("date", "time")}
    if not (visit.get("date") and visit.get("time")):
        return dict(visit)  # no time to keep
    out = {k: v for k, v in visit.items() if k not in ("date", "time")}
    out["when"] = visit_time.to_when(visit["date"], visit["time"], _location_of(locations, visit.get("location_id")))
    return out


_CARD_CODES_BEFORE = {"SinPilas": "NoBatteries", "CarFullSinPilas": "CarFullNoBatteries"}


def _told(visit: dict, locations: list[dict]) -> dict:
    """A visit as it is told: with the day and the time of the wall clock of its location, from its instant, beside it. The card and the batteries are told as they
    are written now: a visit kept with SinPilas or CarFullSinPilas says NoBatteries or CarFullNoBatteries."""
    if visit.get("card_batteries_ok") in _CARD_CODES_BEFORE:
        visit = {**visit, "card_batteries_ok": _CARD_CODES_BEFORE[visit["card_batteries_ok"]]}
    if not visit.get("when"):
        return dict(visit)
    date, time = visit_time.to_wall(visit["when"], _location_of(locations, visit.get("location_id")))
    return {**visit, "date": date, "time": time}


def list_visits(root: Path, research_project_id: str, location_id: str | None = None) -> list[dict]:
    """The visits kept for a research project, in the order they were registered — those to one location (found ignoring
    case) when it is given. Empty until one is registered.

    A visit is kept as an instant, `when` (ISO 8601, UTC, with a Z), and told with the day (`date`) and the time (`time`) of the wall clock of its
    location, in the timezone the location says. A file kept with a day and a time only (an earlier version) is moved to instants when it is read —
    in the timezone its locations say, and written back so — and the visits come the same.

    Raises:
        LocalFolderError: the research project id can't be a folder name.
    """
    raw = _raw_visits(root, research_project_id)
    locations = list_locations(root, research_project_id)
    kept = []
    for visit in raw:
        try:
            kept.append(_kept(visit, locations))
        except (KeyError, ValueError, TypeError):
            kept.append(visit)  # not a visit it can read the time of: left as it is
    if kept != raw and raw:
        _write_raw_visits(root, research_project_id, kept)
    visits = [_told(v, locations) for v in kept]
    if location_id is None:
        return visits
    return [v for v in visits if str(v.get("location_id", "")).lower() == location_id.lower()]


def require_research_project(root: Path, research_project_id: str) -> None:
    """Raises LocalFolderError when the research project isn't kept in the collections folder."""
    if not has_research_project(root, research_project_id):
        raise LocalFolderError(f"The research project '{research_project_id}' isn't in the collections folder.")


def write_visit(root: Path, research_project_id: str, visit: dict) -> dict:
    """Registers a visit to a research project that's already kept here — given with the day and the time of the wall clock of its location,
    kept as an instant (see list_visits) and returned told.

    Raises:
        LocalFolderError: the research project isn't there.
    """
    write_visits(root, research_project_id, [visit])
    locations = list_locations(root, research_project_id)
    return _told(_raw_visits(root, research_project_id)[-1], locations)


def list_unknown(root: Path, research_project_id: str) -> list[dict]:
    """The visits that are unknown — {"location_id", "session"}: the revisions before the first one kept to a site, of which nothing is known (see visit_rules.unknown_records)."""
    return [u for u in _store(root).read_records(research_project_id, "unknown_visits") if u.get("location_id") and u.get("session")]


def _write_unknown(root: Path, research_project_id: str, unknown: list[dict]) -> None:
    if unknown:
        _store(root).write_records(research_project_id, "unknown_visits", unknown)
    else:
        _store(root).delete_records(research_project_id, "unknown_visits")


def write_unknown(root: Path, research_project_id: str, new: list[dict]) -> int:
    """Keeps more unknown visits — those already kept are not repeated; returns how many were added.

    Raises:
        LocalFolderError: the research project isn't there."""
    require_research_project(root, research_project_id)
    have = list_unknown(root, research_project_id)
    keys = {(u["location_id"].lower(), u["session"].upper()) for u in have}
    added = [{"location_id": u["location_id"], "session": u["session"].upper()} for u in new if (u["location_id"].lower(), u["session"].upper()) not in keys]
    if added:
        _write_unknown(root, research_project_id, [*have, *added])
    return len(added)


def update_visit(root: Path, research_project_id: str, location_id: str, session: str, visit: dict) -> dict:
    """Replaces a visit kept — found by its site (ignoring case) and its revision, which is its key and does not change — with `visit`, given with the day and the
    time of the wall clock of its location; the deployment it closed, when it has one, stays. Returned told.

    Raises:
        LocalFolderError: the research project isn't there, or it has no visit to that site in that revision."""
    require_research_project(root, research_project_id)
    locations = list_locations(root, research_project_id)
    list_visits(root, research_project_id)  # an earlier file is moved to instants first
    raw = _raw_visits(root, research_project_id)
    index = next((i for i, v in enumerate(raw) if str(v.get("location_id", "")).lower() == location_id.lower() and str(v.get("session") or "").upper() == session.upper()), None)
    if index is None:
        raise LocalFolderError(f"There is no visit to {location_id} in {session}.")
    kept = _kept({**visit, "location_id": raw[index]["location_id"], "session": raw[index]["session"]}, locations)
    if raw[index].get("deployment_id"):
        kept["deployment_id"] = raw[index]["deployment_id"]
    raw[index] = audit.stamped(kept, raw[index])
    _write_raw_visits(root, research_project_id, raw)
    return _told(raw[index], locations)


def write_visits(root: Path, research_project_id: str, new: list[dict]) -> int:
    """Registers several visits at once to a research project that's already kept here; returns how many.

    Raises:
        LocalFolderError: the research project isn't there.
    """
    require_research_project(root, research_project_id)
    if new:
        locations = list_locations(root, research_project_id)
        list_visits(root, research_project_id)  # an earlier file is moved to instants first
        at = audit.now()
        _write_raw_visits(root, research_project_id, _raw_visits(root, research_project_id) + [audit.stamped(_kept(v, locations), None, at) for v in new])
        # a visit that is known takes the place of the unknown one of its site in its revision
        known = {(str(v.get("location_id", "")).lower(), str(v.get("session") or "").upper()) for v in new}
        unknown = list_unknown(root, research_project_id)
        left = [u for u in unknown if (u["location_id"].lower(), u["session"].upper()) not in known]
        if len(left) != len(unknown):
            _write_unknown(root, research_project_id, left)
    return len(new)


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
    list_visits(root, research_project_id)  # an earlier file is moved to instants first
    raw = _raw_visits(root, research_project_id)
    changed = 0
    for visit in raw:
        key = (str(visit.get("location_id", "")).lower(), str(visit.get("when") or ""))
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
    if str(visit.get("status") or "").lower() in ("not revised", "no revisada", "no revisado"):
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
    list_visits(root, research_project_id)  # an earlier file is moved to instants first
    raw = _raw_visits(root, research_project_id)
    locations = list_locations(root, research_project_id)
    visit = next((v for v in raw if str(v.get("location_id", "")).lower() == location_id.lower()
                  and (_told(v, locations).get("date"), _told(v, locations).get("time")) == (date, time)), None)
    if visit is None:
        raise LocalFolderError(f"There is no visit to {location_id} on {date} at {time} in {research_project_id}.")
    if visit.get("deployment_id") != deployment_id:
        visit["deployment_id"] = deployment_id
        audit.touched(visit)
    _write_raw_visits(root, research_project_id, raw)
    return _told(visit, locations)


def location_time(root: Path, research_project_id: str, location_id: str | None) -> dict:
    """The timezone and summer-time setting kept for a location (found ignoring case) — only the ones it has. They belong
    to the location, so they are what every deployment there is read in; empty when it isn't kept, or has neither.

    Raises:
        LocalFolderError: the research project id can't be a folder name.
    """
    return location_time_in(project_dir(root, research_project_id), location_id)


def location_time_in(project_folder: Path, location_id: str | None) -> dict:
    """location_time for a research project's folder, wherever it is: the folder is named by the research project, and the collections folder is the one that holds it."""
    try:
        locations = _store(project_folder.parent).read_records(project_folder.name, "locations")
    except LocalFolderError:
        return {}
    found = next((l for l in locations if location_id and str(l.get("location_id", "")).lower() == location_id.lower()), None)
    return {k: found[k] for k in ("timezone", "ignore_dst") if found and found.get(k) is not None}


# ── the collection's timestamp log ──────────────────────────────────────────
#
#   <collection folder>/<collection>_FileTimestampLog.csv — as wildintel-tools has it
#
#   Deployment,StartDate,StartTime,EndDate,EndTime
#   r0003-dona_0007_b,2024:09:04,13:10:00,2024:11:04,14:28:00
#
# One row per deployment, named in lower case as Trapper keeps its ids: when its images were taken, as the camera's local
# wall-clock time. wildintel-tools' check-deployments reads it.

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


def upsert_timestamp_log(collection_dir: Path, deployment_id: str, start: datetime, end: datetime) -> dict:
    """Puts a deployment's row — its start and end, as wall-clock times — in its collection's
    timestamp log, creating the collection folder (named in its collection.json) and the log if
    need be. The deployment is named in lower case, as Trapper keeps it. Its own row is replaced (compared ignoring case), the others stay.

    Returns {"path", "action": "added" | "updated" | "unchanged", "rows"}.

    Raises:
        LocalFolderError: the log that's there can't be read — it is left as it is — or the
            deployment ends before it starts.
    """
    if end <= start:
        raise LocalFolderError(f"{deployment_id} must start before it ends ({start} → {end}).")
    path = timestamp_log_path(collection_dir)
    rows = read_timestamp_log(path)
    new_row = {
        "Deployment": deployment_id.lower(), "StartDate": start.strftime("%Y:%m:%d"), "StartTime": start.strftime("%H:%M:%S"),
        "EndDate": end.strftime("%Y:%m:%d"), "EndTime": end.strftime("%H:%M:%S"),
    }
    index = next((i for i, row in enumerate(rows) if row["Deployment"].upper() == deployment_id.upper()), None)
    if index is None:
        rows.append(new_row)
        action = "added"
    elif rows[index] == new_row:
        action = "unchanged"
    else:
        rows[index] = new_row
        action = "updated"
    if not collection_dir.is_dir():
        write_collection_metadata(collection_dir, collection_dir.name)
    if action != "unchanged" or not path.is_file():
        with path.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=TIMESTAMP_LOG_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
    return {"path": str(path), "action": action, "rows": len(rows)}


# ── The collection's fieldwork log ──────────────────────────────────────────
#
# <collection>/<collection>_FieldworkLog.csv, beside the timestamp log: one row per deployment with its fields named as Camtrap DP
# names them, what the visits say of it (the sessions and the actions of the visit that left the camera and of the one that
# collected its card), the SD card and the photos counted on it. Times are UTC, with a Z.

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


def upsert_fieldwork_log(collection_dir: Path, row: dict) -> dict:
    """Puts a deployment's row in its collection's fieldwork log, creating the collection folder and the log if need be. Its own row
    (compared ignoring case) is replaced and the others stay; a field the row does not give is written empty.

    Returns {"path", "action": "added" | "updated" | "unchanged", "rows"}.

    Raises:
        LocalFolderError: the log that's there can't be read — it is left as it is — or the row has no deploymentID.
    """
    deployment_id = str(row.get("deploymentID") or "").strip()
    if not deployment_id:
        raise LocalFolderError("A row of the fieldwork log needs its deploymentID.")
    path = fieldwork_log_path(collection_dir)
    rows = read_fieldwork_log(path)
    new_row = {name: str(row.get(name) if row.get(name) is not None else "") for name in FIELDWORK_LOG_FIELDS}
    index = next((i for i, r in enumerate(rows) if r["deploymentID"].upper() == deployment_id.upper()), None)
    if index is None:
        rows.append(new_row)
        action = "added"
    elif rows[index] == new_row:
        action = "unchanged"
    else:
        rows[index] = new_row
        action = "updated"
    if not collection_dir.is_dir():
        write_collection_metadata(collection_dir, collection_dir.name)
    if action != "unchanged" or not path.is_file():
        with path.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDWORK_LOG_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
    return {"path": str(path), "action": action, "rows": len(rows)}
