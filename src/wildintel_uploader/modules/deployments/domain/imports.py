"""Bringing a folder of camera-trap images into a collection — plain Python: what a folder holds and what the deployment form starts from, what a
session folder's timestamp log says of each of its subfolders, what the collection's logs say of a deployment, where a deployment is kept, which
paths can't be used, and the dates as Camtrap DP asks for them.

Only still images are read for their dates and camera; videos are copied with everything else."""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import PurePath
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from wildintel_uploader.modules.deployments.domain import naming
from wildintel_uploader.modules.deployments.domain.models import BadDeploymentName, DeploymentImportError
from wildintel_uploader.modules.deployments.domain.seal import SEAL_FILE  # noqa: F401 — what makes a deployment no longer pending
from wildintel_uploader.modules.fileinfo.domain import models as fileinfo
from wildintel_uploader.modules.fileinfo.domain.models import common_value
from wildintel_uploader.modules.preprocessing.domain.models import PREPROCESSING_LOG_FILE  # noqa: F401 — what makes it pending

IMAGE_EXTENSIONS = set(fileinfo.IMAGE_EXTENSIONS)
TIMESTAMP_LOG_SUFFIX = "_FileTimestampLog.csv"

_PATH_SEGMENT = re.compile(r"^[0-9A-Za-z_.-]+$")
_REVISION_PREFIX = re.compile(r"^r\d{4}-")
_REVISION = re.compile(r"^R(\d{4})-", re.IGNORECASE)
_LOG_DATE = "%Y:%m:%d %H:%M:%S"


def is_image(path: PurePath) -> bool:
    return path.suffix.lower() in IMAGE_EXTENSIONS


# ── names ──

def deployment_id_for(revision: int, location_id: str) -> str:
    """See domain.naming — what it refuses is a DeploymentImportError here."""
    try:
        return naming.deployment_id_for(revision, location_id)
    except BadDeploymentName as exc:
        raise DeploymentImportError(exc.message) from exc


def collection_code(deployment_id: str) -> str:
    """See domain.naming — what it refuses is a DeploymentImportError here."""
    try:
        return naming.collection_code(deployment_id)
    except BadDeploymentName as exc:
        raise DeploymentImportError(exc.message) from exc


def collection_of(root: PurePath, research_project_id: str, deployment_id: str) -> PurePath:
    """Where a deployment's collection lives locally: <collections folder>/<research project id>/<R0003>. Every collection is kept there before being
    uploaded, whatever its destination.

    Raises:
        DeploymentImportError: the research project id can't be a folder name, or the deployment id has no collection prefix."""
    if not _PATH_SEGMENT.match(research_project_id) or research_project_id in {".", ".."}:
        raise DeploymentImportError(
            f"The research project id '{research_project_id}' can only have letters, digits, '_', '-' and '.' to be a folder name."
        )
    return root / research_project_id / collection_code(deployment_id)


# ── the paths ──

def not_a_folder(folder: PurePath) -> DeploymentImportError:
    return DeploymentImportError(f"Not a folder: {folder}")


def check_nesting(source: PurePath, dest: PurePath) -> None:
    """`source` and `dest` resolved. Raises DeploymentImportError when the destination is the source or nested inside it (a copy would recurse into
    its own output)."""
    if source == dest or dest.is_relative_to(source):
        raise DeploymentImportError("The source images folder cannot be the deployment folder or one of its parent folders.")


def is_pending(has_preprocessing_log: bool, has_seal: bool) -> bool:
    """A deployment preprocessed but not consolidated (sealed) yet: one the preprocessing may redo, since nothing has frozen it."""
    return has_preprocessing_log and not has_seal


def check_not_kept(dest: PurePath, synced: bool, has_content: bool) -> None:
    """Raises DeploymentImportError: the deployment was synced from TRAPPER, which is not modified here, or is already kept in dest — importing again
    would mix the images."""
    if synced:
        raise DeploymentImportError(f"{dest.name} was synced from TRAPPER, so it can't be modified here.")
    if has_content:
        raise DeploymentImportError(f"{dest} already exists — importing again would mix the images.")


# ── a folder of images ──

def scan(files: int, images: int) -> dict:
    """What a folder holds, and nothing more: how many files, and how many of them are images."""
    warnings: list[str] = []
    if not files:
        warnings.append("The folder is empty.")
    elif not images:
        warnings.append(f"None of the {files} file(s) look like images.")
    return {"file_count": files, "image_count": images, "warnings": warnings}


def extra_fields(exif_fields: list[str] | None) -> list[str]:
    """The EXIF fields the checks ask beyond the dates and the camera, which are always read."""
    return [f for f in (exif_fields or []) if f.lower() not in fileinfo.CAMERA_FIELDS and f.lower() != "datetimeoriginal"]


def guess(dates: list[datetime | None], models: list[str | None], ids: list[str | None], reader: str) -> dict:
    """The deployment form's starting point, from what the images say — one date, model and id for each image: the date range, and the camera
    model and id when every image agrees on them (a folder mixing cameras has no single one to suggest). "warnings" says what couldn't be read."""
    images = len(dates)
    known = [d for d in dates if d is not None]
    warnings: list[str] = []
    if not images:
        warnings.append("There are no images to read — the dates must be entered by hand.")
    elif len(known) < images:
        warnings.append(f"{images - len(known)} of {images} image(s) have no readable EXIF date.")
    if images:
        distinct_models = {m for m in models if m}
        distinct_ids = {i for i in ids if i}
        if len(distinct_models) > 1:
            warnings.append(f"The images come from {len(distinct_models)} different camera models — the camera model was left blank.")
        if len(distinct_ids) > 1:
            warnings.append(f"The images come from {len(distinct_ids)} different camera ids — the camera id was left blank.")
        if reader == "pillow":
            warnings.append("ExifTool isn't installed, so the camera id (serial number) may be missing — install it for a fuller reading.")
    return {
        "start_date": min(known).isoformat() if known else None,
        "end_date": max(known).isoformat() if known else None,
        "camera_model": common_value(models),
        "camera_id": common_value(ids),
        "warnings": warnings,
    }


# ── a session folder: one subfolder per deployment, and its timestamp log ──

def no_subfolders() -> DeploymentImportError:
    return DeploymentImportError("This folder has no subfolders — a collection has one subfolder per deployment.")


def loose_warnings(loose: int) -> list[str]:
    return [f"{loose} loose file(s) beside the subfolders will be ignored."] if loose else []


def is_timestamp_log(name: str) -> bool:
    return name.lower().endswith(TIMESTAMP_LOG_SUFFIX.lower())


def timestamp_log_of(folder_name: str, names: list[str]) -> tuple[str | None, list[str]]:
    """The <collection>_FileTimestampLog.csv wildintel-tools expects beside a collection's deployments, among the names of the folder's files: the
    one named after the folder, else the only one there. None — with a warning saying why — otherwise."""
    named = f"{folder_name}{TIMESTAMP_LOG_SUFFIX}"
    if named in names:
        return named, []
    found = sorted(n for n in names if is_timestamp_log(n))
    if len(found) == 1:
        return found[0], []
    if found:
        return None, [f"There are {len(found)} FileTimestampLog files ({', '.join(found)}) and none is named after the folder — none was used."]
    return None, [f"No timestamp log ({named}) was found in the collection folder, so the dates can't be recovered from it."]


def timestamp_log_name(collection: str) -> str:
    return f"{collection}{TIMESTAMP_LOG_SUFFIX}"


def unreadable_log(why: object) -> list[str]:
    return [f"{why} — its dates were not used."]


def periods(log_name: str, rows: list[dict]) -> tuple[dict[str, tuple[str, datetime, datetime]], list[str]]:
    """The log's rows as {lower-cased deployment id: (deployment id as written, start, end)}, and a warning for each row that can't be used (a date
    that isn't like 2024:09:04 13:10:00, or one that ends before it starts)."""
    warnings: list[str] = []
    found: dict[str, tuple[str, datetime, datetime]] = {}
    for row in rows:
        try:
            start = datetime.strptime(f"{row['StartDate']} {row['StartTime']}", _LOG_DATE)
            end = datetime.strptime(f"{row['EndDate']} {row['EndTime']}", _LOG_DATE)
        except ValueError:
            warnings.append(f"{log_name}: the dates of {row['Deployment']} are not like 2024:09:04 13:10:00 — that row was ignored.")
            continue
        if end <= start:
            warnings.append(f"{log_name}: {row['Deployment']} ends before it starts — that row was ignored.")
            continue
        found[row["Deployment"].lower()] = (row["Deployment"], start, end)
    return found, warnings


def session_deployment(name: str, path: str, scanned: dict) -> dict:
    return {"name": name, "path": path, **scanned, "start_date": None, "end_date": None, "from_timestamp_log": False, "log_deployment_id": None}


def match_log(deployments: list[dict], found: dict[str, tuple[str, datetime, datetime]]) -> dict:
    """Gives each subfolder the log has a row for — by its name, or by a deployment id like R0033-<name> — its start and end, and says so. What the
    log matched: {"rows", "matched", "unmatched" (the ids of the rows no subfolder matches, as written), "revision"} — the revision every matched id
    starts with (R0033-… → 33), None when they disagree or have none."""
    matched = 0
    used: set[str] = set()
    for deployment in deployments:
        name = deployment["name"].lower()
        # a log written by wildintel-tools names the full deployment id, R0033-DONA_01, for a subfolder DONA_01
        key = name if name in found else next((k for k in found if _REVISION_PREFIX.sub("", k) == name), None)
        period = found.get(key) if key else None
        if period:
            used.add(key)
            deployment["log_deployment_id"] = period[0]
            deployment["start_date"], deployment["end_date"] = period[1].isoformat(), period[2].isoformat()
            deployment["from_timestamp_log"] = True
            matched += 1
    revisions = {int(m.group(1)) for d in deployments if d["log_deployment_id"] and (m := _REVISION.match(d["log_deployment_id"]))}
    revision = next(iter(revisions)) if len(revisions) == 1 and 0 not in revisions else None  # R0000 is not a revision
    return {"rows": len(found), "matched": matched, "revision": revision, "unmatched": [p[0] for k, p in found.items() if k not in used]}


# ── what the collection's logs say of a deployment ──

_FROM_FIELDWORK_LOG: dict[str, tuple[str, type]] = {
    "setupBy": ("setup_by", str), "cameraID": ("camera_id", str), "cameraModel": ("camera_model", str), "cameraDelay": ("camera_interval", int),
    "cameraHeight": ("camera_height", float), "cameraDepth": ("camera_depth", float), "cameraTilt": ("camera_tilt", int),
    "cameraHeading": ("camera_heading", int), "detectionDistance": ("detection_distance", float), "timestampIssues": ("timestamp_issues", bool),
    "baitUse": ("bait_use", bool), "featureType": ("feature_type", str), "habitat": ("habitat", str),
    "deploymentGroups": ("deployment_groups", str), "deploymentComments": ("comments", str),
}


def log_entry(collection: str, deployment_id: str, timestamp_rows: list[dict], fieldwork_rows: list[dict]) -> dict:
    """What the collection's two logs say of a deployment — their row with its id, compared ignoring case — or nothing where there is none:
    {"collection", "timestamps": {"start", "end"} | None (the camera's wall-clock time, ISO), "fieldwork": {"start", "end" (UTC),
    "details": the fields of the deployment it fills in} | None}."""
    wanted = deployment_id.lower()
    timestamps = None
    for row in timestamp_rows:
        if row["Deployment"].lower() == wanted and row["StartDate"] and row["EndDate"]:
            # the log writes its dates as the camera does (2024:09:04): ISO here
            timestamps = {"start": f"{row['StartDate'].replace(':', '-')}T{row['StartTime'] or '00:00:00'}",
                          "end": f"{row['EndDate'].replace(':', '-')}T{row['EndTime'] or '00:00:00'}"}
    fieldwork = None
    for row in fieldwork_rows:
        if row["deploymentID"].lower() != wanted:
            continue
        details: dict = {}
        for column, (field, kind) in _FROM_FIELDWORK_LOG.items():
            cell = row.get(column, "")
            if not cell:
                continue
            try:
                details[field] = (cell.lower() == "true") if kind is bool else kind(cell)
            except ValueError:
                continue
        if row.get("deploymentTags"):
            details["tags"] = [t.strip() for t in row["deploymentTags"].split("|") if t.strip()]
        fieldwork = {"start": row.get("deploymentStart") or None, "end": row.get("deploymentEnd") or None, "details": details}
    return {"collection": collection, "timestamps": timestamps, "fieldwork": fieldwork}


# ── the dates, as Camtrap DP asks for them ──

def with_timezone(local_iso: str | None, tz_name: str) -> str | None:
    """A local timestamp ("2024-09-04T13:10:00", as read from EXIF) stamped with the UTC offset the IANA timezone had at that moment
    ("2024-09-04T13:10:00+02:00") — the designator Camtrap DP asks for. Anything that already carries one is left alone.

    Raises:
        DeploymentImportError: tz_name isn't a known IANA timezone."""
    if not local_iso:
        return local_iso
    try:
        zone = ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise DeploymentImportError(f"Unknown timezone: {tz_name}") from exc
    parsed = datetime.fromisoformat(local_iso)
    if parsed.tzinfo is not None:
        return local_iso
    return parsed.replace(tzinfo=zone).isoformat(timespec="seconds")


# ── the copy ──

def copied(index: int, total: int, name: str) -> dict:
    return {"type": "copy", "index": index, "total": total, "name": name}
