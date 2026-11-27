"""The rules of an upload to TRAPPER — plain Python: which research project and which classification project a revision goes to, what TRAPPER
calls it, which location and deployment are the ones it has, which timezone a package declares, how the images are split into packages, what the
yaml and the deployments csv say, and the words of what is checked.

An upload, as wildintel-tools did it in three commands, in one: the location and the deployment are created in TRAPPER's research project if they
aren't there yet; the deployment's images are packed into a zip and the yaml that describes them, split in several parts if a zip would be bigger
than a size; each zip and its yaml are uploaded, and TRAPPER is told to process them into a collection. Three modes: "upload" does all of it;
"dry_run" only reads TRAPPER and says what it would do; "generate" only writes the files and leaves them."""
from __future__ import annotations

import ast
from datetime import datetime, timezone
from typing import Any, TypeVar

from wildintel_uploader.modules.uploaders.domain.models import UploaderError

T = TypeVar("T")

MODES: tuple[str, ...] = ("upload", "dry_run", "generate")
DEFAULT_MAX_ZIP_BYTES = 500 * 1024 * 1024
WAIT_FOR_COLLECTION_SECONDS = 900  # TRAPPER processes the package in the background
POLL_SECONDS = 5
PACK_REPORT_EVERY = 25  # images between two pack_progress events
PACKAGE_NAME = "package"
DEPLOYMENTS_CSV_SUFFIX = "_deployments.csv"
CSV_FIELDS = ["deploymentID", "locationID", "deploymentStart", "deploymentEnd", "cameraModel", "longitude", "latitude"]


# ── what TRAPPER has ──

def research_project_pk(projects: list[dict], record: dict) -> int:
    """The research project's pk in TRAPPER: the one it was filled in from, or else the one with its acronym.

    Raises:
        UploaderError: TRAPPER has no such research project (it isn't created here)."""
    pk = record.get("trapper_pk")
    if pk is not None and any(p["pk"] == pk for p in projects):
        return pk
    acronym = (record.get("acronym") or "").lower()
    match = next((p for p in projects if (p.get("acronym") or "").lower() == acronym), None)
    if match is None:
        raise UploaderError(f"TRAPPER has no research project '{record.get('acronym')}' — create it there first (research projects aren't created from here).")
    return match["pk"]


def classification_project(projects: list[dict], chosen: int | None) -> dict:
    """The classification project the collection's yaml names (its "project_id" — not the research project's pk): the one chosen, which must
    belong to the research project, or else the only one it has.

    Raises:
        UploaderError: the chosen one isn't one of the research project's, or none was chosen and it has none or several."""
    if chosen is not None:
        found = next((p for p in projects if p["pk"] == chosen), None)
        if found is None:
            raise UploaderError(f"The classification project #{chosen} isn't one of the research project's in TRAPPER.")
        return found
    if not projects:
        raise UploaderError("The research project has no classification project in TRAPPER, and the revision needs one — create it there first.")
    if len(projects) > 1:
        names = ", ".join(f"{p['name']} (#{p['pk']})" for p in projects)
        raise UploaderError(f"The research project has several classification projects — choose which one the revision goes to: {names}.")
    return projects[0]


def needs_location(location_id: str | None) -> str:
    """Raises UploaderError when a deployment has no location: it can't be looked for nor created in TRAPPER."""
    if not location_id:
        raise UploaderError("The deployment has no location id, so its location can't be looked for or created in TRAPPER.")
    return location_id


def location_named(locations: list[dict], location_id: str) -> dict | None:
    """The location as TRAPPER has it — found ignoring case: TRAPPER keeps its ids in lower case —, or None."""
    wanted = location_id.lower()
    return next((loc for loc in locations if loc["location_id"].lower() == wanted), None)


def deployment_named(deployments: list[dict], deployment_id: str) -> dict | None:
    """The deployment as TRAPPER has it — found ignoring case —, or None. A yaml has to name it exactly as TRAPPER does."""
    wanted = deployment_id.lower()
    return next((d for d in deployments if (d["deployment_id"] or "").lower() == wanted), None)


def collection_name(research_project: dict, collection: str) -> str:
    """The name a revision has in TRAPPER: the research project's acronym before it, joined with a hyphen (WICP_02-R0001). TRAPPER compares the
    names of its collections across every research project, so R0001 of one project would be R0001 of all of them."""
    acronym = (research_project.get("acronym") or "").strip()
    if not acronym or collection.lower().startswith(f"{acronym.lower()}-"):
        return collection
    return f"{acronym}-{collection}"


def location_access_problem(location: dict | None, username: str) -> str | None:
    """Why the account may not be able to put a deployment in this location — TRAPPER only takes a deployment whose location the account owns or
    manages — or None when it can (or when TRAPPER doesn't say). A guess: TRAPPER doesn't list a location's managers, so it goes by the owner and by
    whether TRAPPER offers the account to delete the location. Only to explain."""
    if location is None or location.get("can_manage") is None:
        return None
    owner = location.get("owner")
    if location["can_manage"] or (owner and owner.lower() == username.lower()):
        return None
    return (f"The location {location['location_id']} belongs to {owner or 'another user'}, and {username} is neither its owner nor one of its managers, "
            "so TRAPPER may refuse a deployment there. Ask its owner to make this account a manager of the location — or use a location of your own.")


def location_time_settings(location: dict | None, timezone_name: str, ignore_dst: bool) -> tuple[str, bool, str]:
    """The timezone and summer-time setting a package declares — the location's own when it has them, else those given — and a sentence saying so
    when they differ from the ones given ("" when they don't). TRAPPER only accepts a package that declares the ones of its location."""
    if location is None:
        return timezone_name, ignore_dst, ""
    zone = location.get("timezone") or timezone_name
    ignores = ignore_dst if location.get("ignore_dst") is None else bool(location["ignore_dst"])
    if (zone, ignores) == (timezone_name, ignore_dst):
        return zone, ignores, ""
    return zone, ignores, f" Its timezone is {zone} and it {'ignores' if ignores else 'does not ignore'} summer time — the package declares that, as TRAPPER requires."


def link(site: str | None, kind: str, pk: int | None) -> str | None:
    """The page of a location, a deployment or a collection in TRAPPER's own web interface — to check it there."""
    if site is None or pk is None:
        return None
    path = {"location": "geomap/location/detail", "deployment": "geomap/deployment/detail", "collection": "storage/collection/detail"}[kind]
    return f"{site.rstrip('/')}/{path}/{pk}/"


def trapper_message(exc: Exception) -> str:
    """TRAPPER answers a refused task with a dict — {'data': {'message': …, 'errors': …}} — that an exception shows as its repr; this is what it
    says, in words. Anything else is its own text."""
    text = str(exc)
    try:
        parsed = ast.literal_eval(text) if text.lstrip().startswith("{") else None
    except (ValueError, SyntaxError):
        parsed = None
    data = parsed.get("data", parsed) if isinstance(parsed, dict) else None
    if isinstance(data, dict) and (data.get("message") or data.get("errors")):
        return " ".join(str(part).rstrip(".") + "." for part in (data.get("message"), data.get("errors")) if part)
    return text


# ── the deployment kept and its package ──

def preprocessed(deployment_id: str, collection: str, metadata: object, log: object) -> tuple[dict, dict]:
    """The deployment and what its preprocessing recorded — the dates the yaml needs.

    Raises:
        UploaderError: it isn't a deployment kept in the collection, or it wasn't preprocessed."""
    if not isinstance(metadata, dict):
        raise UploaderError(f"{deployment_id} isn't a deployment kept in {collection}: it has no deployment.json.")
    if not isinstance(log, dict) or not log.get("images"):
        raise UploaderError(f"{deployment_id} wasn't preprocessed (no preprocessing.json): import it again through the wizard first.")
    return metadata, log


def images_to_send(deployment: str, log: dict, missing: list[str]) -> list[dict]:
    """The images the preprocessing recorded, all of which must be there (`missing` are those that aren't).

    Raises:
        UploaderError: there are none, or one of them is missing."""
    entries = log.get("images", [])
    if missing:
        raise UploaderError(f"{len(missing)} image(s) the preprocessing recorded are missing from {deployment}: {', '.join(missing[:3])}…")
    if not entries:
        raise UploaderError(f"There are no images to upload in {deployment}.")
    return entries


def split_by_size(items: list[tuple[int, T]], max_bytes: int | None) -> list[list[T]]:
    """Groups of items whose sizes add up to at most max_bytes (one bigger than that goes alone)."""
    if not max_bytes:
        return [[item for _, item in items]] if items else []
    parts: list[list[T]] = []
    current: list[T] = []
    size = 0
    for item_size, item in items:
        if current and size + item_size > max_bytes:
            parts.append(current)
            current, size = [], 0
        current.append(item)
        size += item_size
    if current:
        parts.append(current)
    return parts


def date_recorded(iso: str) -> str:
    """A date as the yaml wants it: ISO 8601 in UTC, "2024-07-01T09:00:00+0000"."""
    parsed = datetime.fromisoformat(iso)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S%z")


def package_base(project_id: int, stamp: str, collection: str, deployment_id: str, part: int) -> str:
    return f"{PACKAGE_NAME}_{project_id}_{stamp}_{collection}_{deployment_id}_part{part:03d}"


def package_definition(collection: str, project_id: int, timezone_name: str, ignore_dst: bool, named: str, resources: list[dict]) -> dict:
    """What TRAPPER reads to build the collection: the classification project's pk, the timezone, the folder of the zip, and the deployment —
    named as TRAPPER has it, in lower case — with its resources."""
    return {"collections": [{
        "name": collection, "project_id": project_id, "timezone": timezone_name, "timezone_ignore_dst": ignore_dst, "resources_dir": collection,
        "deployments": [{"deployment_id": named, "resources": resources}],
    }]}


def resource(name: str, date: str, mime: str, width: int | None, height: int | None, size: int) -> dict:
    return {"name": name, "file": name, "date_recorded": date_recorded(date), "mime_type": mime,
            "file_width": width, "file_height": height, "file_size": size, "file_fps": None, "file_duration": None}


def csv_row(deployment: Any, log: dict) -> dict:
    """A deployment's row of its collection's deployments csv, as wildintel-tools' preparation wrote it: deploymentID, locationID,
    deploymentStart, deploymentEnd (the first and the last image, in UTC) and cameraModel — plus the location's longitude and latitude at the end,
    which TRAPPER's own deployment import needs to create a location."""
    dates = sorted(date_recorded(e["date"]) for e in log.get("images", []) if e.get("date"))
    camera = deployment.camera_model or next((e["camera"] for e in log.get("images", []) if e.get("camera")), "")
    return {"deploymentID": deployment.deployment_id, "locationID": deployment.location_id or "",
            "deploymentStart": dates[0] if dates else deployment.start_date, "deploymentEnd": dates[-1] if dates else deployment.end_date,
            "cameraModel": camera or "", "longitude": deployment.longitude, "latitude": deployment.latitude}


def megabytes(size: float) -> str:
    return f"{size / (1024 * 1024):.1f}"


# ── what is checked before an upload ──

def locations_message(known: set[str], location_ids: list[str] | None) -> str:
    """What the access check says of the locations: how many can be read, and which of those of the deployments are there or would be created."""
    wanted = sorted({i for i in (location_ids or []) if i}, key=str.lower)
    present = [i for i in wanted if i.lower() in known]
    missing = [i for i in wanted if i.lower() not in known]
    message = f"The {len(known)} location(s) of the research project can be read."
    if present:
        message += f" Already in TRAPPER: {', '.join(present)}."
    if missing:
        message += f" Would be created: {', '.join(missing)}."
    return message
