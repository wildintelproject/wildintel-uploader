"""Sync the local collections folder with what Trapper has for a classification project.

Trapper is read, never changed; the collections folder only gets what it is missing — what is already
there is left as it is, whatever Trapper says:

  <collections folder>/<research project id>/research_project.json
                                            /locations.json
                                            /<R0003>/collection.json
                                                    /<R0003>_FileTimestampLog.csv
                                                    /<deployment id>/deployment.json

The collections are those of the classification project whose name starts with R; a deployment of the
research project goes to the one its id starts with (R0003-DONA_01 → R0003). The images are not downloaded, so
there is no preprocessing log; images.json is made from what Trapper holds for each deployment's images (names,
when they were taken, what they show) — not the size, the pixels nor the hashes, which Trapper doesn't have.
"""
from __future__ import annotations

import logging
from collections.abc import Iterator
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import ValidationError

from wildintel_uploader.core.schemas.requests import DeploymentFields, ResearchProjectRecord
from wildintel_uploader.core.services import deployment_import_service, local_folder_service, trapper_service

logger = logging.getLogger(__name__)


def collection_names(credentials: tuple[str, str, str], classification_project_pk: int) -> list[str]:
    """The names of the classification project's collections that start with R, sorted."""
    client = trapper_service.client(*credentials)
    collections = client.classification_projects.where_project_collections(classification_project_pk, page_size=trapper_service.LIST_PAGE_SIZE)
    return sorted({c.name for c in collections if c.name and c.name.upper().startswith("R")}, key=str.lower)


def collections_with_deployments(credentials: tuple[str, str, str], research_project_pk: int, classification_project_pk: int) -> list[dict]:
    """The collections starting with R of the classification project, each {"name", "deployments"}: the ids (upper case)
    of the research project's deployments that belong to it."""
    deployments = trapper_service.list_deployments(*credentials, research_project_pk)
    result = []
    for name in collection_names(credentials, classification_project_pk):
        ids = sorted(deployment_id for deployment_id, _ in _deployments_of(deployments, name))
        result.append({"name": name, "deployments": ids})
    return result


def _deployments_of(deployments: list[dict], collection: str) -> list[tuple[str, dict]]:
    """The (id in upper case, deployment) pairs whose id starts with the collection's code."""
    found = []
    for deployment in deployments:
        deployment_id = (deployment["deployment_id"] or "").upper()  # Trapper has it in lower case
        try:
            code = deployment_import_service.collection_code(deployment_id)
        except deployment_import_service.DeploymentImportError:
            continue
        if code.lower() == collection.lower():
            found.append((deployment_id, deployment))
    return found


def wall_clock(value: str, timezone_name: str | None, ignore_dst: bool) -> datetime:
    """The camera's wall-clock time of an ISO 8601 moment Trapper holds: in the location's timezone, on its standard
    time all year when it ignores summer time. Without a timezone, the time as written."""
    moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if moment.tzinfo is None or not timezone_name:
        return moment.replace(tzinfo=None)
    try:
        zone = ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError):
        return moment.replace(tzinfo=None)
    local = moment.astimezone(zone)
    return local.replace(tzinfo=None) - (local.dst() or timedelta(0) if ignore_dst else timedelta(0))


def deployment_fields(deployment: dict, deployment_id: str) -> DeploymentFields:
    """A deployment as Trapper exports it, as DeploymentFields: the empty values are left out (Trapper gives "" for what
    it doesn't have), the dates' offset is written ±hh:mm (it gives +0000) and the ids are in upper case.

    Raises:
        pydantic.ValidationError: what is left is not a valid deployment.
    """
    given = {k: v for k, v in deployment.items() if k != "pk" and v is not None and v != "" and v != []}
    for key in ("start_date", "end_date"):
        if isinstance(given.get(key), str):
            try:
                given[key] = datetime.fromisoformat(given[key].replace("Z", "+00:00")).isoformat()
            except ValueError:
                pass  # left as it is: the validation says what is wrong
    if given.get("location_id"):
        given["location_id"] = given["location_id"].upper()
    return DeploymentFields.model_validate({**given, "deployment_id": deployment_id})


def image_entries(resources: list[dict], timezone_name: str | None, ignore_dst: bool) -> list[dict]:
    """What images.json keeps of the images Trapper holds for a deployment, in order of when they were taken:
    the name and when (the camera's wall clock in the location's timezone) and, as extras, Trapper's pk, the instant as
    Trapper has it and its epoch seconds, the mime and what they show."""
    entries = []
    for r in resources:
        taken = r.get("date_recorded")
        local = stamp = None
        if taken:
            try:
                local = wall_clock(str(taken), timezone_name, ignore_dst).isoformat()
                moment = datetime.fromisoformat(str(taken).replace("Z", "+00:00"))
                stamp = moment.timestamp() if moment.tzinfo else None
            except ValueError:
                pass
        entries.append(local_folder_service.image_entry(r["name"], local, "trapper", {
            "trapper_pk": r["pk"], "taken_at": taken, "timestamp": stamp, "mime": r.get("mime"),
            "date_recorded_correct": r.get("date_recorded_correct"), "observation_type": r.get("observation_type", []),
            "species": r.get("species", []), "tags": r.get("tags", []),
        }))
    return sorted(entries, key=lambda e: (e["local_time"] or "", e["name"]))


def sync_stream(
    credentials: tuple[str, str, str], root: Path, research_project: dict, classification_project_pk: int,
    only: list[str] | None = None, only_deployments: list[str] | None = None,
) -> Iterator[dict]:
    """Creates, under root, what Trapper has for the classification project and the folder lacks — one deployment at a time.

    research_project is {"pk", "name", "acronym"} — the one the classification project belongs to.
    only limits the sync to the collections of those names (any case), and only_deployments to the deployments of
    those ids (any case); None syncs them all.
    The deployments' and locations' ids, which Trapper keeps in lower case, are written in upper case.

    Yields {"type": "progress", "message"} as each step starts or ends, and last {"type": "done", ...} with the lists
    of what was "created" and what was already there ("kept") for each kind, the deployments no collection of the
    classification project claims ("unassigned"), and those Trapper holds in a way that is not a valid deployment
    ("failed": {"deployment_id", "error"}), which are left out.

    Raises:
        local_folder_service.LocalFolderError: the research project can't be a folder name.
    """
    def say(message: str) -> dict:
        return {"type": "progress", "message": message}

    project_id = research_project.get("acronym") or str(research_project["pk"])
    folder = local_folder_service.project_dir(root, project_id)
    created: dict[str, list[str]] = {"research_project": [], "locations": [], "collections": [], "deployments": [], "timestamp_log": [], "images": []}
    kept: dict[str, list[str]] = {key: [] for key in created}

    if (folder / local_folder_service.RESEARCH_PROJECT_METADATA_FILE).is_file():
        kept["research_project"].append(project_id)
        yield say(f"Research project {project_id}: already there.")
    else:
        record = ResearchProjectRecord.model_construct(name=research_project.get("name") or project_id, acronym=project_id, trapper_pk=research_project["pk"])
        local_folder_service.write_research_project(root, record.model_dump())
        created["research_project"].append(project_id)
        yield say(f"Research project {project_id}: created.")

    yield say("Reading the locations from Trapper…")
    locations = trapper_service.list_locations(*credentials, research_project["pk"])
    known = {l.get("location_id", "").lower() for l in local_folder_service.list_locations(root, project_id)}
    by_id = {}
    for location in locations:
        by_id[location["location_id"].lower()] = location
        if location["location_id"].lower() in known:
            kept["locations"].append(location["location_id"].upper())
            continue
        record = {k: location.get(k) for k in ("location_id", "name", "timezone", "ignore_dst", "latitude", "longitude")}
        # Trapper keeps the ids in lower case; here they are written as the wizard does, in upper case.
        local_folder_service.write_location(root, project_id, {**record, "location_id": location["location_id"].upper(), "coordinate_uncertainty": None, "trapper_pk": location["pk"]})
        created["locations"].append(location["location_id"].upper())
    yield say(f"Locations: {len(created['locations'])} created, {len(kept['locations'])} already there.")

    yield say("Reading the deployments and collections from Trapper…")
    deployments = trapper_service.list_deployments(*credentials, research_project["pk"])
    names = collection_names(credentials, classification_project_pk)
    if only is not None:
        wanted = {n.lower() for n in only}
        names = [n for n in names if n.lower() in wanted]
    claimed: set[str] = set()
    failed: list[dict] = []
    for number, name in enumerate(names, 1):
        collection_dir = folder / name
        if (collection_dir / local_folder_service.COLLECTION_METADATA_FILE).is_file():
            kept["collections"].append(name)
        else:
            local_folder_service.write_collection_metadata(collection_dir, name)
            created["collections"].append(name)
        mine = _deployments_of(deployments, name)
        claimed.update(deployment_id for deployment_id, _ in mine)  # not "unassigned" even if left out here
        if only_deployments is not None:
            wanted_ids = {d.upper() for d in only_deployments}
            mine = [(deployment_id, d) for deployment_id, d in mine if deployment_id in wanted_ids]
        yield say(f"Collection {name} ({number}/{len(names)}): {len(mine)} deployment(s).")
        log_rows = {row["Deployment"].upper() for row in local_folder_service.read_timestamp_log(local_folder_service.timestamp_log_path(collection_dir))}
        for position, (deployment_id, deployment) in enumerate(mine, 1):
            prefix = f"{deployment_id} ({position}/{len(mine)})"
            target = collection_dir / deployment_id
            if (target / local_folder_service.DEPLOYMENT_METADATA_FILE).is_file():
                kept["deployments"].append(deployment_id)
            else:
                try:
                    fields = deployment_fields(deployment, deployment_id)
                except ValidationError as exc:  # one deployment Trapper holds badly doesn't stop the rest
                    error = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())
                    failed.append({"deployment_id": deployment_id, "error": error})
                    yield say(f"{prefix}: skipped, Trapper holds it with invalid values ({error}).")
                    continue
                local_folder_service.write_deployment_metadata(target, fields.model_dump())
                created["deployments"].append(deployment_id)
            if (target / local_folder_service.IMAGES_FILE).is_file():
                kept["images"].append(deployment_id)
            else:
                yield say(f"{prefix}: reading its images from Trapper…")
                location = by_id.get((deployment.get("location_id") or "").lower(), {})
                resources = trapper_service.list_deployment_resources(*credentials, deployment["pk"])
                entries = image_entries(resources, location.get("timezone"), bool(location.get("ignore_dst")))
                local_folder_service.write_images_file(target, deployment_id, entries, source="trapper")
                created["images"].append(deployment_id)
            if deployment_id.upper() in log_rows:
                kept["timestamp_log"].append(deployment_id)
            elif deployment.get("start_date") and deployment.get("end_date"):
                location = by_id.get((deployment.get("location_id") or "").lower(), {})
                tz, dst = location.get("timezone"), bool(location.get("ignore_dst"))
                start, end = wall_clock(deployment["start_date"], tz, dst), wall_clock(deployment["end_date"], tz, dst)
                try:
                    local_folder_service.upsert_timestamp_log(collection_dir, deployment_id, start, end)
                    created["timestamp_log"].append(deployment_id)
                except local_folder_service.LocalFolderError as exc:
                    logger.warning("%s: no timestamp log row: %s", deployment_id, exc)
            yield say(f"{prefix}: done.")

    unassigned = sorted(d["deployment_id"].upper() for d in deployments if d["deployment_id"] and d["deployment_id"].upper() not in claimed)
    yield {"type": "done", "research_project_id": project_id, "folder": str(folder), "created": created, "kept": kept, "unassigned": unassigned, "failed": failed, "collections": names}


def sync(
    credentials: tuple[str, str, str], root: Path, research_project: dict, classification_project_pk: int,
    only: list[str] | None = None, only_deployments: list[str] | None = None,
) -> dict:
    """sync_stream run to its end: what it created and kept, without the progress."""
    result: dict = {}
    for event in sync_stream(credentials, root, research_project, classification_project_pk, only, only_deployments):
        if event["type"] == "done":
            result = {k: v for k, v in event.items() if k != "type"}
    return result
