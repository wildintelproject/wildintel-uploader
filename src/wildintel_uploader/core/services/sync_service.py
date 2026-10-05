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
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from wildintel_uploader.core.schemas.requests import DeploymentFields, ResearchProjectRecord
from wildintel_uploader.core.services import deployment_import_service, local_folder_service, trapper_service

logger = logging.getLogger(__name__)


def collection_names(credentials: tuple[str, str, str], classification_project_pk: int) -> list[str]:
    """The names of the classification project's collections that start with R, sorted."""
    client = trapper_service.client(*credentials)
    collections = client.classification_projects.where_project_collections(classification_project_pk, page_size=trapper_service.LIST_PAGE_SIZE)
    return sorted({c.name for c in collections if c.name and c.name.upper().startswith("R")}, key=str.lower)


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


def image_entries(resources: list[dict], timezone_name: str | None, ignore_dst: bool) -> list[dict]:
    """What images.json keeps of the images Trapper holds for a deployment, in order of when they were taken:
    the name, Trapper's pk, when (the camera's wall clock in the location's timezone, the instant as Trapper has it and
    its epoch seconds), the mime and what they show."""
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
        entries.append({
            "name": r["name"], "trapper_pk": r["pk"], "local_time": local, "taken_at": taken, "timestamp": stamp, "mime": r.get("mime"),
            "date_recorded_correct": r.get("date_recorded_correct"), "observation_type": r.get("observation_type", []),
            "species": r.get("species", []), "tags": r.get("tags", []),
        })
    return sorted(entries, key=lambda e: (e["local_time"] or "", e["name"]))


def sync(
    credentials: tuple[str, str, str], root: Path, research_project: dict, classification_project_pk: int,
) -> dict:
    """Creates, under root, what Trapper has for the classification project and the folder lacks.

    research_project is {"pk", "name", "acronym"} — the one the classification project belongs to.
    Returns the lists of what was "created" and what was already there ("kept") for each kind, and the
    deployments no collection of the classification project claims ("unassigned").

    Raises:
        local_folder_service.LocalFolderError: the research project can't be a folder name.
    """
    project_id = research_project.get("acronym") or str(research_project["pk"])
    folder = local_folder_service.project_dir(root, project_id)
    created: dict[str, list[str]] = {"research_project": [], "locations": [], "collections": [], "deployments": [], "timestamp_log": [], "images": []}
    kept: dict[str, list[str]] = {key: [] for key in created}

    if (folder / local_folder_service.RESEARCH_PROJECT_METADATA_FILE).is_file():
        kept["research_project"].append(project_id)
    else:
        record = ResearchProjectRecord.model_construct(name=research_project.get("name") or project_id, acronym=project_id, trapper_pk=research_project["pk"])
        local_folder_service.write_research_project(root, record.model_dump())
        created["research_project"].append(project_id)

    locations = trapper_service.list_locations(*credentials, research_project["pk"])
    known = {l.get("location_id", "").lower() for l in local_folder_service.list_locations(root, project_id)}
    by_id = {}
    for location in locations:
        by_id[location["location_id"].lower()] = location
        if location["location_id"].lower() in known:
            kept["locations"].append(location["location_id"])
            continue
        record = {k: location.get(k) for k in ("location_id", "name", "timezone", "ignore_dst", "latitude", "longitude")}
        local_folder_service.write_location(root, project_id, {**record, "coordinate_uncertainty": None, "trapper_pk": location["pk"]})
        created["locations"].append(location["location_id"])

    deployments = trapper_service.list_deployments(*credentials, research_project["pk"])
    names = collection_names(credentials, classification_project_pk)
    claimed: set[str] = set()
    for name in names:
        collection_dir = folder / name
        if (collection_dir / local_folder_service.COLLECTION_METADATA_FILE).is_file():
            kept["collections"].append(name)
        else:
            local_folder_service.write_collection_metadata(collection_dir, name)
            created["collections"].append(name)
        log_rows = {row["Deployment"].upper() for row in local_folder_service.read_timestamp_log(local_folder_service.timestamp_log_path(collection_dir))}
        for deployment in deployments:
            deployment_id = deployment["deployment_id"] or ""
            try:
                code = deployment_import_service.collection_code(deployment_id)
            except deployment_import_service.DeploymentImportError:
                continue
            if code.lower() != name.lower():
                continue
            claimed.add(deployment_id)
            target = collection_dir / deployment_id
            if (target / local_folder_service.DEPLOYMENT_METADATA_FILE).is_file():
                kept["deployments"].append(deployment_id)
            else:
                fields = DeploymentFields.model_validate({k: v for k, v in deployment.items() if k != "pk" and v is not None})
                local_folder_service.write_deployment_metadata(target, fields.model_dump())
                created["deployments"].append(deployment_id)
            if (target / local_folder_service.IMAGES_FILE).is_file():
                kept["images"].append(deployment_id)
            else:
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

    unassigned = sorted(d["deployment_id"] for d in deployments if d["deployment_id"] and d["deployment_id"] not in claimed)
    return {"research_project_id": project_id, "folder": str(folder), "created": created, "kept": kept, "unassigned": unassigned, "collections": names}
