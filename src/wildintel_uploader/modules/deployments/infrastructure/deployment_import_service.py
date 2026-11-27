"""Importing a deployment: organize a folder of camera-trap images locally
(config.collections_dir()), then register the deployment in Trapper from the form
the caller filled in (the uploaders register it in TRAPPER).

v1 scope: registers the deployment's metadata only — it does not upload the
images themselves to Trapper (that's a separate, not yet built, option).
Only still images are scanned for EXIF dates; video files are copied along
with everything else but don't contribute to the date range or camera model
guess (no bundled exiftool — see the "Import deployment" doc page)."""
from __future__ import annotations

import logging
import re
import shutil
from collections.abc import Iterator
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from pathlib import Path

from PIL import Image

from wildintel_uploader.modules.deployments.infrastructure.plugs import config
from wildintel_uploader.shared.camtrap import DeploymentFields
from wildintel_uploader.modules.deployments.domain import naming as _naming
from wildintel_uploader.modules.deployments.domain.models import BadDeploymentName, DeploymentsFailed
from wildintel_uploader.modules.fileinfo.domain import models as _fileinfo
from wildintel_uploader.modules.deployments.infrastructure import collections as layout
from wildintel_uploader.modules.fileinfo.domain.models import common_value


def _files():
    """What is known of the files of the images (the contract of modules.fileinfo), from where the app is put together."""
    from wildintel_uploader.modules.deployments.infrastructure import plugs
    return plugs.file_info()

logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS = set(_fileinfo.IMAGE_EXTENSIONS)


class DeploymentImportError(DeploymentsFailed, ValueError):
    """A problem with the source/destination paths — reported to the user, not a bug. One of what the deployments refuse (their domain's
    DeploymentsFailed), so that the other modules tell it by that."""


_PATH_SEGMENT = re.compile(r"^[0-9A-Za-z_.-]+$")


def deployment_id_for(revision: int, location_id: str) -> str:
    """See modules.deployments.domain.naming — what it refuses is a DeploymentImportError here, as it was."""
    try:
        return _naming.deployment_id_for(revision, location_id)
    except BadDeploymentName as exc:
        raise DeploymentImportError(exc.message) from exc


def collection_code(deployment_id: str) -> str:
    """See modules.deployments.domain.naming — what it refuses is a DeploymentImportError here, as it was."""
    try:
        return _naming.collection_code(deployment_id)
    except BadDeploymentName as exc:
        raise DeploymentImportError(exc.message) from exc


_FROM_FIELDWORK_LOG: dict[str, tuple[str, type]] = {
    "setupBy": ("setup_by", str), "cameraID": ("camera_id", str), "cameraModel": ("camera_model", str), "cameraDelay": ("camera_interval", int),
    "cameraHeight": ("camera_height", float), "cameraDepth": ("camera_depth", float), "cameraTilt": ("camera_tilt", int),
    "cameraHeading": ("camera_heading", int), "detectionDistance": ("detection_distance", float), "timestampIssues": ("timestamp_issues", bool),
    "baitUse": ("bait_use", bool), "featureType": ("feature_type", str), "habitat": ("habitat", str),
    "deploymentGroups": ("deployment_groups", str), "deploymentComments": ("comments", str),
}


def log_entry(research_project_id: str, deployment_id: str) -> dict:
    """What the collection's two logs say of a deployment — their row with its id, compared ignoring case — or nothing where there is none:
    {"collection", "timestamps": {"start", "end"} | None (the camera's wall-clock time, ISO), "fieldwork": {"start", "end" (UTC),
    "details": the fields of DeploymentFields it fills in} | None}. A log that can't be read says so as LocalFolderError."""
    collection = default_collection_dir(research_project_id, deployment_id)
    wanted = deployment_id.lower()
    timestamps = None
    for row in layout.read_timestamp_log(layout.timestamp_log_path(collection)):
        if row["Deployment"].lower() == wanted and row["StartDate"] and row["EndDate"]:
            # the log writes its dates as the camera does (2024:09:04): ISO here
            timestamps = {"start": f"{row['StartDate'].replace(':', '-')}T{row['StartTime'] or '00:00:00'}",
                          "end": f"{row['EndDate'].replace(':', '-')}T{row['EndTime'] or '00:00:00'}"}
    fieldwork = None
    for row in layout.read_fieldwork_log(layout.fieldwork_log_path(collection)):
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
    return {"collection": collection.name, "timestamps": timestamps, "fieldwork": fieldwork}


def default_collection_dir(research_project_id: str, deployment_id: str) -> Path:
    """Where a deployment's collection lives locally by default:
    <collections folder>/<research project id>/<R0003>. Every collection is
    kept here before being uploaded, whatever its destination.

    Raises:
        DeploymentImportError: the research project id can't be a folder name,
            or the deployment id has no collection prefix.
    """
    if not _PATH_SEGMENT.match(research_project_id) or research_project_id in {".", ".."}:
        raise DeploymentImportError(
            f"The research project id '{research_project_id}' can only have letters, digits, '_', '-' and '.' to be a folder name."
        )
    return config.collections_dir() / research_project_id / collection_code(deployment_id)


def is_pending(dest: Path) -> bool:
    """Whether dest holds a deployment that was preprocessed but not consolidated (sealed) yet — one that preprocessing may
    redo, since nothing has frozen it."""
    return (dest / "preprocessing.json").is_file() and not (dest / "seal.json").exists()


def check_not_kept(dest: Path) -> None:
    """Raises:
        DeploymentImportError: the deployment is already kept in dest — importing again would mix the images — or it
            was synced from Trapper, which is not modified here.
    """
    if layout.is_synced(dest):
        raise DeploymentImportError(f"{dest.name} was synced from TRAPPER, so it can't be modified here.")
    if dest.exists() and any(dest.iterdir()):
        raise DeploymentImportError(f"{dest} already exists — importing again would mix the images.")


def existing_deployment_dir(research_project_id: str, deployment_id: str) -> Path | None:
    """The folder where this deployment is already kept — <collections folder>/<research project>/<R0003>/<deployment id>
    — if it is there with something in it, which is when importing it again would be refused. None otherwise,
    or if the ids can't name a folder."""
    try:
        dest = default_collection_dir(research_project_id, deployment_id) / deployment_id
    except DeploymentImportError:
        return None
    try:
        return dest if dest.is_dir() and any(dest.iterdir()) and not is_pending(dest) else None
    except OSError:
        return None


def check_paths(source_dir: Path, dest_dir: Path) -> None:
    """Raises:
        DeploymentImportError: the source doesn't exist, isn't a directory,
            or the destination is the source or nested inside it (which
            would make an rglob-based copy recurse into its own output).
    """
    if not source_dir.is_dir():
        raise DeploymentImportError(f"Not a folder: {source_dir}")
    try:
        source_resolved = source_dir.resolve()
        dest_resolved = dest_dir.resolve()
    except OSError as exc:
        raise DeploymentImportError(f"Could not resolve the path: {exc}") from exc
    if source_resolved == dest_resolved or dest_resolved.is_relative_to(source_resolved):
        raise DeploymentImportError(
            "The source images folder cannot be the deployment folder or one of its parent folders."
        )


def _image_datetime(path: Path) -> datetime | None:
    """The capture date of one image (see modules.fileinfo). For many, read them all at once with read_dates: one run of ExifTool for all."""
    return _files().dates([path]).get(path)


def _files_and_images(source_dir: Path) -> tuple[list[Path], list[Path]]:
    files = [p for p in source_dir.rglob("*") if p.is_file()]
    return files, [p for p in files if p.suffix.lower() in IMAGE_EXTENSIONS]


def scan_folder(source_dir: Path) -> dict:
    """What a folder holds, and nothing more: how many files, and how many of them are images (by their
    extension). Reading the images is the job of the steps that follow — the validation, and guess_details
    for the deployment form's starting point.

    Raises:
        DeploymentImportError: source_dir doesn't exist or isn't a folder.
    """
    if not source_dir.is_dir():
        raise DeploymentImportError(f"Not a folder: {source_dir}")
    files, images = _files_and_images(source_dir)
    warnings: list[str] = []
    if not files:
        warnings.append("The folder is empty.")
    elif not images:
        warnings.append(f"None of the {len(files)} file(s) look like images.")
    return {"file_count": len(files), "image_count": len(images), "warnings": warnings}


def prefetch_metadata(source_dir: Path, exif_fields: list[str] | None = None) -> None:
    """Starts reading the EXIF of a folder's images in the background (see modules.fileinfo) — what the checks, the details and the preprocessing
    will ask —, right after it is scanned: while the user chooses the checks, ExifTool is already reading. Nothing happens if it is not a folder."""
    if not source_dir.is_dir():
        return
    _, images = _files_and_images(source_dir)
    extra = [f for f in (exif_fields or []) if f.lower() not in _fileinfo.CAMERA_FIELDS and f.lower() != "datetimeoriginal"]
    _files().prefetch(images, extra)


def guess_details(source_dir: Path) -> dict:
    """The deployment form's starting point, read from the images' metadata: the date range (the earliest and
    latest capture date) and the camera model and id — the last two only when every image agrees on them (a
    folder mixing cameras has no single one to suggest). "warnings" says what couldn't be read.

    Raises:
        DeploymentImportError: source_dir doesn't exist or isn't a folder.
    """
    if not source_dir.is_dir():
        raise DeploymentImportError(f"Not a folder: {source_dir}")
    files, images = _files_and_images(source_dir)

    dates: list[datetime] = []
    dated_images = 0
    for dt in _files().dates(images).values():
        if dt is not None:
            dates.append(dt)
            dated_images += 1

    cameras, reader = _files().cameras(images)
    models = [cameras[p].model for p in images]
    ids = [cameras[p].camera_id for p in images]
    camera_model = common_value(models)
    camera_id = common_value(ids)

    warnings: list[str] = []
    if not images:
        warnings.append("There are no images to read — the dates must be entered by hand.")
    elif dated_images < len(images):
        warnings.append(f"{len(images) - dated_images} of {len(images)} image(s) have no readable EXIF date.")
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
        "start_date": min(dates).isoformat() if dates else None,
        "end_date": max(dates).isoformat() if dates else None,
        "camera_model": camera_model,
        "camera_id": camera_id,
        "warnings": warnings,
    }


def _find_timestamp_log(session_dir: Path) -> tuple[Path | None, list[str]]:
    """The <collection>_FileTimestampLog.csv wildintel-tools expects beside a collection's deployments: the one
    named after the folder, else the only one there. None (and a warning when it is ambiguous) otherwise."""
    suffix = layout.TIMESTAMP_LOG_SUFFIX
    named = session_dir / f"{session_dir.name}{suffix}"
    if named.is_file():
        return named, []
    found = sorted(p for p in session_dir.iterdir() if p.is_file() and p.name.lower().endswith(suffix.lower()))
    if len(found) == 1:
        return found[0], []
    if found:
        return None, [f"There are {len(found)} FileTimestampLog files ({', '.join(p.name for p in found)}) and none is named after the folder — none was used."]
    return None, []


def _timestamp_log_periods(path: Path) -> tuple[dict[str, tuple[str, datetime, datetime]], list[str]]:
    """The log's rows as {lower-cased deployment id: (deployment id as written, start, end)}, plus a warning for
    each row that can't be used (a date that isn't %Y:%m:%d %H:%M:%S, or one that ends before it starts)."""
    warnings: list[str] = []
    try:
        rows = layout.read_timestamp_log(path)
    except layout.LocalFolderError as exc:
        return {}, [f"{exc} — its dates were not used."]
    periods: dict[str, tuple[str, datetime, datetime]] = {}
    for row in rows:
        try:
            start = datetime.strptime(f"{row['StartDate']} {row['StartTime']}", "%Y:%m:%d %H:%M:%S")
            end = datetime.strptime(f"{row['EndDate']} {row['EndTime']}", "%Y:%m:%d %H:%M:%S")
        except ValueError:
            warnings.append(f"{path.name}: the dates of {row['Deployment']} are not like 2024:09:04 13:10:00 — that row was ignored.")
            continue
        if end <= start:
            warnings.append(f"{path.name}: {row['Deployment']} ends before it starts — that row was ignored.")
            continue
        periods[row["Deployment"].lower()] = (row["Deployment"], start, end)
    return periods, warnings


def scan_session(session_dir: Path) -> dict:
    """A session folder — one subfolder per deployment — scanned: each subfolder's own scan_folder result (its files
    and images), named after it (hidden ones are left out), and how many loose files sit beside them.

    If the folder holds a <collection>_FileTimestampLog.csv (the file wildintel-tools asks for beside a
    collection's deployments), the start and end of each subfolder it has a row for — by the subfolder's
    name, or by a deployment id like R0033-<name> — have them given as "start_date" and "end_date" (the others
    don't: they are read from the images when the details are asked for, see guess_details), and
    that deployment says so in "from_timestamp_log" and gives the id the row names it by in
    "log_deployment_id" (None otherwise). "timestamp_log" is then {"name", "path", "rows", "matched",
    "unmatched" (the ids of the rows no subfolder matches), "revision"} — the revision number every matched id starts with (R0033-… → 33), None if they
    disagree or have none — or None when there is no usable log.

    Raises:
        DeploymentImportError: session_dir doesn't exist, isn't a folder, or has no subfolders.
    """
    if not session_dir.is_dir():
        raise DeploymentImportError(f"Not a folder: {session_dir}")
    subfolders = sorted((p for p in session_dir.iterdir() if p.is_dir() and not p.name.startswith(".")), key=lambda p: p.name.lower())
    if not subfolders:
        raise DeploymentImportError("This folder has no subfolders — a collection has one subfolder per deployment.")
    suffix = layout.TIMESTAMP_LOG_SUFFIX.lower()  # a timestamp log is not a stray file
    loose = sum(1 for p in session_dir.iterdir() if p.is_file() and not p.name.startswith(".") and not p.name.lower().endswith(suffix))
    warnings = [f"{loose} loose file(s) beside the subfolders will be ignored."] if loose else []
    deployments = [{"name": p.name, "path": str(p), **scan_folder(p), "start_date": None, "end_date": None, "from_timestamp_log": False, "log_deployment_id": None} for p in subfolders]

    timestamp_log = None
    log_path, log_warnings = _find_timestamp_log(session_dir)
    warnings += log_warnings
    if log_path is None and not log_warnings:  # none at all: the dates will have to come from elsewhere
        warnings.append(f"No timestamp log ({session_dir.name}{layout.TIMESTAMP_LOG_SUFFIX}) was found in the collection folder, so the dates can't be recovered from it.")
    if log_path is not None:
        periods, log_warnings = _timestamp_log_periods(log_path)
        warnings += log_warnings
        matched = 0
        used: set[str] = set()
        for deployment in deployments:
            name = deployment["name"].lower()
            # A log written by wildintel-tools names the full deployment id, R0033-DONA_01, for a subfolder DONA_01.
            key = name if name in periods else next((k for k in periods if re.sub(r"^r\d{4}-", "", k) == name), None)
            period = periods.get(key) if key else None
            if period:
                used.add(key)
                deployment["log_deployment_id"] = period[0]
                deployment["start_date"], deployment["end_date"] = period[1].isoformat(), period[2].isoformat()
                deployment["from_timestamp_log"] = True
                matched += 1
        revisions = {int(m.group(1)) for d in deployments if d["log_deployment_id"] and (m := re.match(r"^R(\d{4})-", d["log_deployment_id"], re.IGNORECASE))}
        revision = next(iter(revisions)) if len(revisions) == 1 and 0 not in revisions else None  # R0000 is not a revision
        # The rows no subfolder is named after, as written in the log — the page says so after its table of subfolders.
        unmatched = [period[0] for key, period in periods.items() if key not in used]
        timestamp_log = {"name": log_path.name, "path": str(log_path), "rows": len(periods), "matched": matched, "revision": revision, "unmatched": unmatched}
    return {"deployments": deployments, "loose_files": loose, "warnings": warnings, "timestamp_log": timestamp_log}


def with_timezone(local_iso: str | None, tz_name: str) -> str | None:
    """A local timestamp ("2024-09-04T13:10:00", as read from EXIF) stamped
    with the UTC offset the IANA timezone had at that moment
    ("2024-09-04T13:10:00+02:00") — the designator Camtrap DP asks for.
    Anything that already carries one is left alone.

    Raises:
        DeploymentImportError: tz_name isn't a known IANA timezone.
    """
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


_natural_key = _naming.natural_key


def copy_folder(source_dir: Path, dest_dir: Path) -> Iterator[dict]:
    """Copies source_dir's files into dest_dir, preserving its subfolder
    structure — never touches the source (shutil.copy2, a copy, not a
    move). Yields {"type": "copy", "index", "total", "name"} as each file
    finishes."""
    files = [p for p in source_dir.rglob("*") if p.is_file()]
    for index, path in enumerate(files, start=1):
        relative = path.relative_to(source_dir)
        target = dest_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        yield {"type": "copy", "index": index, "total": len(files), "name": str(relative)}


def organize_stream(research_project_id: str, source_dir: str, deployment: DeploymentFields) -> tuple[Path, Iterator[dict]]:
    """Organizes source_dir's images under <collections folder>/<research project id>/<collection>/<deployment_id> (see default_collection_dir), with
    the collection's and deployment's metadata beside them as JSON — the same local layout as the "Local folder" destination. Returns where they go,
    and the events of the copy: {"type": "copy", "index", "total", "name"} as each file is copied.

    Raises:
        DeploymentImportError: bad source/destination paths — checked before anything is copied.
    """
    source = Path(source_dir).expanduser()
    collection = default_collection_dir(research_project_id, deployment.deployment_id)
    dest = collection / deployment.deployment_id
    check_paths(source, dest)

    def events() -> Iterator[dict]:
        layout.write_collection_metadata(collection, collection.name)
        yield from copy_folder(source, dest)
        layout.write_deployment_metadata(dest, deployment.model_dump())

    return dest, events()


def copied_images_info(dest: Path) -> list[dict]:
    """The images of a copied deployment folder, in natural order, as images.json keeps them: the name, the camera's
    wall-clock time from the EXIF (None when it has none) and, as extras, the camera and its serial number, the file's size and its pixels — what
    the EXIF says, so that what comes after does not read the images again (#140); the dates and the camera in one ExifTool run."""
    entries = []
    ordered = sorted((p for p in dest.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS), key=lambda p: _natural_key(p.relative_to(dest)))
    dates = _files().dates(ordered)
    cameras, _ = _files().cameras(ordered)   # read with the dates: no other run
    for path in ordered:
        taken = dates[path]
        try:
            with Image.open(path) as img:
                width, height = img.width, img.height
        except Exception:
            width = height = None
        entries.append(layout.image_entry(
            str(path.relative_to(dest)), taken.isoformat() if taken else None, "local",
            {"camera": cameras[path].model, "camera_id": cameras[path].camera_id, "width": width, "height": height, "size_bytes": path.stat().st_size},
        ))
    return entries


def seal_deployment(source: Path, dest: Path, deployment: DeploymentFields, **details) -> bool:
    """Checks the source images and seals the deployment kept in dest (see application.seal). A failure is logged and the
    deployment is left without a seal — it was imported all the same — and False says so."""
    from wildintel_uploader.modules.deployments.infrastructure import plugs  # the seal of the deployments, from where the app is put together runs this module's own checks
    try:
        plugs.sealing().seal(source, dest, deployment, **details)
        return True
    except Exception as exc:
        logger.warning("Could not seal %s: %s", deployment.deployment_id, exc, exc_info=True)
        return False


def import_local_stream(source_dir: str, collection_dir: str, collection_name: str | None, deployment: DeploymentFields) -> Iterator[dict]:
    """Organizes source_dir's images under collection_dir/<deployment_id>,
    and records the collection's and deployment's own metadata as JSON —
    the "Local folder" destination, with no Trapper account involved.
    Events: the same "copy" shape as organize_stream, and "done", with no
    "registering" step.

    Raises:
        DeploymentImportError: bad source/destination paths, or the deployment is already kept.
    """
    source = Path(source_dir).expanduser()
    collection = Path(collection_dir).expanduser()
    dest = collection / deployment.deployment_id
    check_paths(source, dest)
    check_not_kept(dest)

    def events() -> Iterator[dict]:
        layout.write_collection_metadata(collection, collection_name)
        yield from copy_folder(source, dest)
        layout.write_deployment_metadata(dest, deployment.model_dump())
        layout.write_images_file(dest, deployment.deployment_id, copied_images_info(dest))
        yield {"type": "sealing"}
        sealed = seal_deployment(source, dest, deployment)
        logger.info("Deployment %s organized locally in %s", deployment.deployment_id, dest)
        yield {"type": "done", "dest_dir": str(dest), "sealed": sealed}

    return events()
