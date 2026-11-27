"""The rules of a sync with TRAPPER — plain Python. TRAPPER is read, never changed; the collections folder only gets what it is missing.

The collections are those of the classification project whose name starts with R; a deployment of the research project goes to the one its id
starts with (R0003-DONA_01 → R0003). TRAPPER keeps its ids in lower case: they are written here in upper case, as the wizard does. The images
are not downloaded unless asked, so there is no preprocessing: what TRAPPER holds of each image — its name, when it was taken, what it shows —
is kept as it says it."""
from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from wildintel_uploader.modules.catalog.domain.models import Location, ResearchProject
from wildintel_uploader.modules.deployments.domain.models import BadDeploymentName
from wildintel_uploader.modules.deployments.domain.naming import collection_code

DOWNLOAD_WORKERS = 4    # images downloaded at once
PROGRESS_EVERY = 25     # a message each so many images


def revisions(names: list[str]) -> list[str]:
    """The names of a classification project's collections that start with R — each once —, sorted."""
    return sorted({n for n in names if n and n.upper().startswith("R")}, key=str.lower)


def deployments_of(deployments: list[dict], collection: str) -> list[tuple[str, dict]]:
    """The (id in upper case, deployment) pairs of TRAPPER whose id starts with the collection's code."""
    found = []
    for deployment in deployments:
        deployment_id = (deployment["deployment_id"] or "").upper()
        try:
            code = collection_code(deployment_id)
        except BadDeploymentName:
            continue
        if code.lower() == collection.lower():
            found.append((deployment_id, deployment))
    return found


def wall_clock(value: str, timezone_name: str | None, ignore_dst: bool) -> datetime:
    """The camera's wall-clock time of an ISO 8601 moment TRAPPER holds: in the location's timezone, on its standard time all year when it ignores
    summer time. Without a timezone, the time as written."""
    moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if moment.tzinfo is None or not timezone_name:
        return moment.replace(tzinfo=None)
    try:
        zone = ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError):
        return moment.replace(tzinfo=None)
    local = moment.astimezone(zone)
    return local.replace(tzinfo=None) - (local.dst() or timedelta(0) if ignore_dst else timedelta(0))


def new_project(research_project: dict, project_id: str) -> ResearchProject:
    """A research project TRAPPER has, as one made by hand starts — the fields of TRAPPER's form at their first option —, with the pk it has there."""
    return ResearchProject(acronym=project_id, name=research_project.get("name") or project_id, status="active", trapper_pk=research_project["pk"])


def new_location(location: dict) -> Location:
    """A location TRAPPER has, as it is kept here: its id in upper case, pending until a visit is made to it."""
    return Location(location_id=location["location_id"].upper(), name=location.get("name"), timezone=location.get("timezone"),
                    ignore_dst=location.get("ignore_dst"), latitude=location.get("latitude"), longitude=location.get("longitude"),
                    trapper_pk=location["pk"], status="pending")


def deployment_record(deployment: dict, deployment_id: str) -> dict:
    """A deployment as TRAPPER exports it, as a deployment is kept: the empty values left out (TRAPPER gives "" for what it doesn't have), the
    dates' offset written ±hh:mm (it gives +0000) and the ids in upper case. What is left is checked when it is kept."""
    given = {k: v for k, v in deployment.items() if k != "pk" and v is not None and v != "" and v != []}
    for key in ("start_date", "end_date"):
        if isinstance(given.get(key), str):
            try:
                given[key] = datetime.fromisoformat(given[key].replace("Z", "+00:00")).isoformat()
            except ValueError:
                pass   # left as it is: the check says what is wrong
    if given.get("location_id"):
        given["location_id"] = given["location_id"].upper()
    return {**given, "deployment_id": deployment_id}


def images_held(resources: list[dict], timezone_name: str | None, ignore_dst: bool) -> list[tuple[str, str | None, dict]]:
    """What is kept of the images TRAPPER holds for a deployment — (name, when it was taken by the camera's wall clock, extras: TRAPPER's pk, the
    instant as TRAPPER has it and its epoch seconds, the mime and what they show) —, in order of when they were taken."""
    out = []
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
        out.append((r["name"], local, {"trapper_pk": r["pk"], "taken_at": taken, "timestamp": stamp, "mime": r.get("mime"),
                                       "date_recorded_correct": r.get("date_recorded_correct"), "observation_type": r.get("observation_type", []),
                                       "species": r.get("species", []), "tags": r.get("tags", [])}))
    return sorted(out, key=lambda e: (e[1] or "", e[0]))


def plain_name(name: str) -> bool:
    """Whether a file's name is only a name — one that would not leave the deployment's folder."""
    return bool(name) and "/" not in name and "\\" not in name and name not in (".", "..")
