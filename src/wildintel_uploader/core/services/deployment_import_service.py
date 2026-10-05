"""Importing a deployment: organize a folder of camera-trap images locally
(config.collections_dir()), then register the deployment in Trapper from the form
the caller filled in (see trapper_service.import_deployment).

v1 scope: registers the deployment's metadata only — it does not upload the
images themselves to Trapper (that's a separate, not yet built, option).
Only still images are scanned for EXIF dates; video files are copied along
with everything else but don't contribute to the date range or camera model
guess (no bundled exiftool — see the "Import deployment" doc page)."""
from __future__ import annotations

import hashlib
import logging
import re
import shutil
import tempfile
from collections import defaultdict
from collections.abc import Iterator
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from pathlib import Path

from PIL import ExifTags, Image

from wildintel_uploader.core import config
from wildintel_uploader.core.schemas.requests import DeploymentFields
from wildintel_uploader.core.services import camera_info, local_folder_service, trapper_service

logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".tif", ".tiff"}
_EXIF_IFD = 0x8769  # the "Exif" sub-IFD, where DateTimeOriginal lives
_TAG_IDS = {name: tag for tag, name in ExifTags.TAGS.items()}


class DeploymentImportError(ValueError):
    """A problem with the source/destination paths — reported to the user,
    not a bug."""


_COLLECTION_PREFIX = re.compile(r"^(R\d{4})-")
_PATH_SEGMENT = re.compile(r"^[0-9A-Za-z_.-]+$")


def deployment_id_for(revision: int, location_id: str) -> str:
    """The deployment id wildintel-tools expects: R + the revision as four
    digits, a hyphen and the location id — "R0003-DONA_01".

    Raises:
        DeploymentImportError: the revision isn't 1..9999 or the location is empty.
    """
    if not 1 <= revision <= 9999 or not location_id.strip():
        raise DeploymentImportError("A deployment id needs a revision from 1 to 9999 and a location id.")
    return f"R{revision:04d}-{location_id.strip()}"


def collection_code(deployment_id: str) -> str:
    """The collection a deployment belongs to — its id's "R0003" prefix.

    Raises:
        DeploymentImportError: the id doesn't start with R + four digits + a hyphen.
    """
    match = _COLLECTION_PREFIX.match(deployment_id)
    if not match:
        raise DeploymentImportError(
            f"The deployment id '{deployment_id}' must start with its collection, R + four digits + a hyphen (e.g. R0003-DONA_01)."
        )
    return match.group(1)


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
    try:
        with Image.open(path) as img:
            exif = img.getexif()
            raw = exif.get(_TAG_IDS.get("DateTimeOriginal", 36867))
            if raw is None:
                sub = exif.get_ifd(_EXIF_IFD)
                raw = sub.get(_TAG_IDS.get("DateTimeOriginal", 36867))
            if raw is None:
                raw = exif.get(_TAG_IDS.get("DateTime", 306))
            if not raw:
                return None
            return datetime.strptime(str(raw).strip(), "%Y:%m:%d %H:%M:%S")
    except Exception as exc:  # a corrupt/unreadable file mustn't stop the scan
        logger.debug("No EXIF date in %s: %s", path, exc)
        return None


def _image_camera_model(path: Path) -> str | None:
    try:
        with Image.open(path) as img:
            exif = img.getexif()
            make = exif.get(_TAG_IDS.get("Make", 271))
            model = exif.get(_TAG_IDS.get("Model", 272))
            parts = [str(p).strip() for p in (make, model) if p]
            return " ".join(parts) or None
    except Exception:
        return None


def scan_folder(source_dir: Path) -> dict:
    """A folder's file count, and the date range / camera model and id guessed
    from its images' metadata — the deployment form's starting point. The
    camera model and id are only filled in when every image agrees on them
    (a folder mixing cameras has no single one to suggest).

    Raises:
        DeploymentImportError: source_dir doesn't exist or isn't a folder.
    """
    if not source_dir.is_dir():
        raise DeploymentImportError(f"Not a folder: {source_dir}")

    files = [p for p in source_dir.rglob("*") if p.is_file()]
    images = [p for p in files if p.suffix.lower() in IMAGE_EXTENSIONS]

    dates: list[datetime] = []
    dated_images = 0
    for path in images:
        dt = _image_datetime(path)
        if dt is not None:
            dates.append(dt)
            dated_images += 1

    cameras, reader = camera_info.read_cameras(images)
    models = [cameras[p].model for p in images]
    ids = [cameras[p].camera_id for p in images]
    camera_model = camera_info.common_value(models)
    camera_id = camera_info.common_value(ids)

    warnings: list[str] = []
    if not files:
        warnings.append("The folder is empty.")
    elif not images:
        warnings.append(f"None of the {len(files)} file(s) look like images — start/end dates must be entered by hand.")
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
        "file_count": len(files),
        "image_count": len(images),
        "start_date": min(dates).isoformat() if dates else None,
        "end_date": max(dates).isoformat() if dates else None,
        "camera_model": camera_model,
        "camera_id": camera_id,
        "warnings": warnings,
    }


def scan_session(session_dir: Path) -> dict:
    """A session folder — one subfolder per deployment — scanned: each subfolder's own scan_folder result,
    named after it (hidden ones are left out), and how many loose files sit beside them.

    Raises:
        DeploymentImportError: session_dir doesn't exist, isn't a folder, or has no subfolders.
    """
    if not session_dir.is_dir():
        raise DeploymentImportError(f"Not a folder: {session_dir}")
    subfolders = sorted((p for p in session_dir.iterdir() if p.is_dir() and not p.name.startswith(".")), key=lambda p: p.name.lower())
    if not subfolders:
        raise DeploymentImportError("This folder has no subfolders — a session has one subfolder per deployment.")
    loose = sum(1 for p in session_dir.iterdir() if p.is_file() and not p.name.startswith("."))
    warnings = [f"{loose} loose file(s) beside the subfolders will be ignored."] if loose else []
    return {
        "deployments": [{"name": p.name, "path": str(p), **scan_folder(p)} for p in subfolders],
        "loose_files": loose,
        "warnings": warnings,
    }


_TRAILING_DIGITS_RE = re.compile(r"(\d+)(?!.*\d)")  # a filename's last run of digits — how camera traps number shots


def _sequence_number(path: Path) -> int | None:
    match = _TRAILING_DIGITS_RE.search(path.stem)
    return int(match.group(1)) if match else None


def _corruption_error(path: Path) -> str | None:
    """None if the file opens and fully decodes; otherwise PIL's error."""
    try:
        with Image.open(path) as img:
            img.load()
        return None
    except Exception as exc:
        return str(exc)


# The image checks validate_images can run — see its own docstring. A
# caller may ask for any subset; None (the default) means all of them.
IMAGE_CHECKS = frozenset({"corrupted", "sequence", "structure", "camera", "exif", "duplicates"})


def _content_hash(path: Path) -> str | None:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        logger.debug("Could not read %s to look for duplicates: %s", path, exc)
        return None
    return digest.hexdigest()


def _duplicate_groups(images: list[Path], source_dir: Path) -> list[dict]:
    """Groups of images with exactly the same content. Files can only be
    equal if they're the same size, so only those are hashed."""
    by_size: dict[int, list[Path]] = defaultdict(list)
    for path in sorted(images):
        try:
            by_size[path.stat().st_size].append(path)
        except OSError:
            continue
    groups: list[dict] = []
    for size, paths in by_size.items():
        if len(paths) < 2:
            continue
        by_hash: dict[str, list[Path]] = defaultdict(list)
        for path in paths:
            digest = _content_hash(path)
            if digest is not None:
                by_hash[digest].append(path)
        groups += [{"size": size, "files": [str(p.relative_to(source_dir)) for p in same]} for same in by_hash.values() if len(same) > 1]
    return sorted(groups, key=lambda g: g["files"][0])


def validate_images(source_dir: Path, checks: frozenset[str] | None = None) -> dict:
    """Independent, opt-in checks over a scanned folder's images — only
    "checked_count" plus whichever of these were asked for are present in
    the result:
      - corrupted: files that fail to fully decode.
      - sequence_issues: camera traps number shots in the order they were
        taken, so within one folder a higher-numbered file shouldn't have
        an earlier EXIF date than a lower-numbered one — that disagreement
        usually means a camera clock reset, a misnamed file, or images
        from two different cards mixed together. Undated or unnumbered
        images are skipped, and each folder is checked on its own since a
        re-used card commonly restarts numbering per folder.
      - subdirectories: folders other than source_dir itself holding
        files — some deployments expect every image directly in one flat
        folder.
      - cameras: the distinct camera (model and id) among the images, with
        how many each took and a few example files — a deployment is one
        camera, so more than one means images from different cameras got
        mixed together. "cameras_without_info" counts the images with no
        camera information at all, and "exiftool" says whether ExifTool (which
        reads the serial number of most camera traps) did the reading.
      - exif_missing: the EXIF fields the rest of the wizard needs — the
        capture date ("date", for the deployment's dates and the order and
        range checks), the camera "camera_model" and the camera id
        ("camera_id", its serial number) — each with how many images lack it
        and a few example files.
      - duplicates: groups of two or more files with exactly the same
        content (a card copied twice, a file renamed and kept), each with
        the size and the files. Only files of the same size are compared,
        so a big folder isn't hashed in full.

    Raises:
        DeploymentImportError: source_dir doesn't exist or isn't a folder.
    """
    if not source_dir.is_dir():
        raise DeploymentImportError(f"Not a folder: {source_dir}")
    checks = IMAGE_CHECKS if checks is None else (checks & IMAGE_CHECKS)

    files = [p for p in source_dir.rglob("*") if p.is_file()]
    images = [p for p in files if p.suffix.lower() in IMAGE_EXTENSIONS]
    result: dict = {"checked_count": len(images)}

    # The camera is read once, for both the checks that need it.
    cameras: dict[Path, camera_info.CameraInfo] = {}
    reader = "pillow"
    if "camera" in checks or "exif" in checks:
        cameras, reader = camera_info.read_cameras(images)
        result["exiftool"] = reader == "exiftool"

    if "exif" in checks:
        missing: dict[str, list[Path]] = {"date": [], "camera_model": [], "camera_id": []}
        for path in sorted(images):
            if _image_datetime(path) is None:
                missing["date"].append(path)
            if cameras[path].model is None:
                missing["camera_model"].append(path)
            if cameras[path].camera_id is None:
                missing["camera_id"].append(path)
        result["exif_missing"] = {
            field: {"count": len(paths), "examples": [str(p.relative_to(source_dir)) for p in paths[:3]]} for field, paths in missing.items()
        }

    if "duplicates" in checks:
        result["duplicates"] = _duplicate_groups(images, source_dir)

    if "camera" in checks:
        groups: dict[tuple[str | None, str | None], list[Path]] = defaultdict(list)
        without_info = 0
        for path in sorted(images):  # a stable order, whatever the file system lists first
            info = cameras[path]
            if info.known:
                groups[(info.model, info.camera_id)].append(path)
            else:
                without_info += 1
        result["cameras"] = [
            {"model": model, "camera_id": camera_id, "count": len(paths), "examples": [str(p.relative_to(source_dir)) for p in paths[:3]]}
            for (model, camera_id), paths in sorted(groups.items(), key=lambda item: (-len(item[1]), item[0][0] or "", item[0][1] or ""))
        ]
        result["cameras_without_info"] = without_info

    if "structure" in checks:
        result["subdirectories"] = sorted({str(p.parent.relative_to(source_dir)) for p in files if p.parent != source_dir})

    need_dates = "sequence" in checks
    if "corrupted" in checks or need_dates:
        corrupted: list[dict] = []
        dated: dict[Path, datetime] = {}
        by_dir: dict[Path, list[Path]] = defaultdict(list)
        for path in images:
            error = _corruption_error(path) if "corrupted" in checks else None
            if error is not None:
                corrupted.append({"path": str(path.relative_to(source_dir)), "error": error})
                continue
            if need_dates:
                by_dir[path.parent].append(path)
                dt = _image_datetime(path)
                if dt is not None:
                    dated[path] = dt
        if "corrupted" in checks:
            result["corrupted"] = corrupted

        if need_dates:
            sequence_issues: list[dict] = []
            for group in by_dir.values():
                numbered = [(path, _sequence_number(path)) for path in group if path in dated]
                numbered = [(path, num) for path, num in numbered if num is not None]
                numbered.sort(key=lambda pair: pair[1])
                for (path_a, num_a), (path_b, num_b) in zip(numbered, numbered[1:]):
                    if num_a != num_b and dated[path_b] < dated[path_a]:
                        sequence_issues.append({
                            "path_a": str(path_a.relative_to(source_dir)), "index_a": num_a, "date_a": dated[path_a].isoformat(),
                            "path_b": str(path_b.relative_to(source_dir)), "index_b": num_b, "date_b": dated[path_b].isoformat(),
                        })
            result["sequence_issues"] = sequence_issues

    return result


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


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        # EXIF dates are the camera's local wall-clock time, so the
        # designator is dropped to compare like with like.
        return datetime.fromisoformat(value).replace(tzinfo=None)
    except ValueError:
        return None


# The postvalidation checks validate_deployment_consistency can run — those
# that need what the wizard knows of the deployment. None (the default) means
# all of them.
DEPLOYMENT_CHECKS = frozenset({"deployment_id", "collection_prefix", "collection_name", "location", "time_range", "camera"})

# wildintel-tools' own naming rules (see its check_collections): a deployment
# is "R0033-DONA_01[_suffix]" and lives in a collection "R0033[_suffix]".
_DEPLOYMENT_ID_RE = re.compile(r"^R[0-9]{4}-([0-9A-Za-z_-]+)(_.+)?$")
_COLLECTION_NAME_RE = re.compile(r"^R[0-9]{4}(_.+)?$")
DEFAULT_TOLERANCE_HOURS = 1.0


def _natural_key(path: Path) -> list:
    """Sorts "IMG_2" before "IMG_10" — the order wildintel-tools walks a deployment's images in."""
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", str(path))]


def _ok(message: str) -> dict:
    return {"ok": True, "message": message}


def _problem(message: str) -> dict:
    return {"ok": False, "message": message}


def _collection_of(deployment_id: str) -> str | None:
    match = re.match(r"^(R[0-9]{4})-", deployment_id)
    return match.group(1) if match else None


def validate_deployment_consistency(
    source_dir: Path, deployment: DeploymentFields, checks: frozenset[str] | None = None, *,
    collection_name: str | None = None, expected_location_id: str | None = None,
    tolerance_hours: float = DEFAULT_TOLERANCE_HOURS,
) -> dict:
    """The postvalidation: checks a deployment — what the wizard now knows of
    it — and its scanned images against wildintel-tools' own rules. Only
    "checked_count" plus whichever of these were asked for are present in the
    result. The naming checks each give {"ok", "message"}:
      - deployment_id: the id looks like R0033-DONA_01 — R, four digits, a
        hyphen, the location id and an optional _suffix.
      - collection_prefix: its R0033 prefix is the collection it goes in.
      - collection_name: the collection is named R0033 (optionally _suffix).
        For a Trapper deployment the collection is the id's own prefix; for a
        local one it's the collection folder's name (collection_name).
      - location: the id's location (the part after the first hyphen, minus an
        optional _suffix) is expected_location_id, the location chosen before.
    The dates are checked, as wildintel-tools does, image by image, in natural
    file-name order, on the camera's wall-clock time:
      - out_of_range: the first image must be within tolerance_hours of
        start_date, the last within tolerance_hours of end_date, and every
        other one between start_date and end_date, each side widened by the
        tolerance. Each item has the file, its date, which rule ("first",
        "last", "between") and the range it should have fallen in.
      - tolerance_hours: what was used.
    And, unchanged:
      - camera_mismatches: images whose EXIF camera model differs from the
        deployment's declared camera_model (skipped if it isn't set).
      - camera_models_found: every distinct EXIF camera model seen.

    Raises:
        DeploymentImportError: source_dir doesn't exist or isn't a folder, or
            tolerance_hours is negative.
    """
    if not source_dir.is_dir():
        raise DeploymentImportError(f"Not a folder: {source_dir}")
    if tolerance_hours < 0:
        raise DeploymentImportError("The tolerance can't be negative.")
    checks = DEPLOYMENT_CHECKS if checks is None else (checks & DEPLOYMENT_CHECKS)

    images = [p for p in source_dir.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS]
    result: dict = {"checked_count": len(images)}
    deployment_id = deployment.deployment_id
    # A Trapper deployment has no collection folder of its own: it goes in the one its id names.
    collection = collection_name if collection_name is not None else _collection_of(deployment_id)

    if "deployment_id" in checks:
        result["deployment_id"] = (
            _ok(f"'{deployment_id}' is a valid deployment id.") if _DEPLOYMENT_ID_RE.match(deployment_id)
            else _problem(f"'{deployment_id}' must look like R0033-DONA_01: R, four digits, a hyphen, the location id and an optional _suffix.")
        )

    if "collection_name" in checks:
        if collection is None:
            result["collection_name"] = _problem("There is no collection: the deployment id doesn't start with one (R0033-…).")
        elif _COLLECTION_NAME_RE.match(collection):
            result["collection_name"] = _ok(f"'{collection}' is a valid collection name.")
        else:
            result["collection_name"] = _problem(f"The collection '{collection}' must be named like R0033 (R and four digits, optionally _suffix).")

    if "collection_prefix" in checks:
        prefix = _collection_of(deployment_id)
        collection_code = collection[:5] if collection is not None and _COLLECTION_NAME_RE.match(collection) else None
        if prefix is None:
            result["collection_prefix"] = _problem(f"'{deployment_id}' doesn't start with a collection (R0033-…).")
        elif collection_code is None:
            result["collection_prefix"] = _problem("There is no valid collection to compare the deployment id's prefix with.")
        elif prefix.lower() != collection_code.lower():
            result["collection_prefix"] = _problem(f"The deployment id starts with {prefix}, but it goes in the collection {collection_code}.")
        else:
            result["collection_prefix"] = _ok(f"The deployment id starts with its collection, {collection_code}.")

    if "location" in checks:
        tail = deployment_id.split("-", 1)[1] if "-" in deployment_id else ""
        if not expected_location_id:
            result["location"] = _ok("No location was chosen to compare with.")
        elif tail.lower() == expected_location_id.lower() or tail.lower().startswith(expected_location_id.lower() + "_"):
            result["location"] = _ok(f"The deployment id's location is {expected_location_id}, the one chosen.")
        else:
            result["location"] = _problem(f"The deployment id's location is '{tail}', but the location chosen is {expected_location_id}.")

    if "time_range" in checks:
        result["tolerance_hours"] = tolerance_hours
        start = _parse_iso(deployment.start_date)
        end = _parse_iso(deployment.end_date)
        tolerance = timedelta(hours=tolerance_hours)
        label = f"{tolerance_hours:g}h"
        out_of_range: list[dict] = []
        ordered = sorted(images, key=lambda p: _natural_key(p.relative_to(source_dir)))
        for position, path in enumerate(ordered):
            dt = _image_datetime(path)
            if dt is None or start is None or end is None:
                continue
            if position == 0:
                rule, low, high = "first", start - tolerance, start + tolerance
                expected = f"{start.isoformat()} ± {label}"
            elif position == len(ordered) - 1:
                rule, low, high = "last", end - tolerance, end + tolerance
                expected = f"{end.isoformat()} ± {label}"
            else:
                rule, low, high = "between", start - tolerance, end + tolerance
                expected = f"{start.isoformat()} – {end.isoformat()} ± {label}"
            if not low <= dt <= high:
                out_of_range.append({"path": str(path.relative_to(source_dir)), "date": dt.isoformat(), "rule": rule, "expected": expected})
        result["out_of_range"] = out_of_range

    if "camera" in checks:
        camera_mismatches: list[dict] = []
        models_found: set[str] = set()
        for path in images:
            model = _image_camera_model(path)
            if model is None:
                continue
            models_found.add(model)
            if deployment.camera_model and model != deployment.camera_model:
                camera_mismatches.append({"path": str(path.relative_to(source_dir)), "detected": model})
        result["camera_mismatches"] = camera_mismatches
        result["camera_models_found"] = sorted(models_found)

    return result


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


def import_stream(
    url: str, username: str, password: str,
    research_project_pk: int, classification_project_pk: int | None,
    source_dir: str, deployment: DeploymentFields, timezone: str | None, *,
    research_project_id: str, ignore_dst: bool = False, register: bool = True,
) -> Iterator[dict]:
    """Organizes source_dir's images under <collections folder>/<research
    project id>/<collection>/<deployment_id> (see default_collection_dir), with
    the collection's and deployment's metadata beside them as JSON — the same
    local layout as the "Local folder" destination — then, unless the deployment already exists in Trapper (register=False —
    it's only being read, not created or changed), registers it. Events:
      - {"type": "copy", "index", "total", "name"}: one file copied.
      - {"type": "registering"}: the local copy is done, Trapper is next
        (skipped entirely when register is false).
      - {"type": "done", "dest_dir"}: dest_dir is where the images ended
        up, for the "now upload them" step this app doesn't have yet.

    Raises:
        DeploymentImportError: bad source/destination paths, or register is
            true but no timezone was given.
        trapper_client.err.APIError: Trapper refused the deployment (e.g. a
            duplicate deployment_id) — nothing already copied is undone.
    """
    source = Path(source_dir).expanduser()
    collection = default_collection_dir(research_project_id, deployment.deployment_id)
    dest = collection / deployment.deployment_id
    check_paths(source, dest)
    if register and not timezone:
        raise DeploymentImportError("A timezone is required to register a new deployment.")

    def events() -> Iterator[dict]:
        local_folder_service.write_collection_metadata(collection, collection.name)
        yield from copy_folder(source, dest)
        local_folder_service.write_deployment_metadata(dest, deployment.model_dump())
        if register:
            yield {"type": "registering"}
            with tempfile.TemporaryDirectory() as tmp:
                csv_path = Path(tmp) / "deployment.csv"
                trapper_service.import_deployment(
                    url, username, password, research_project_pk, classification_project_pk,
                    deployment, timezone, csv_path, ignore_dst=ignore_dst,
                )
            logger.info("Deployment %s registered in Trapper (files organized in %s)", deployment.deployment_id, dest)
        else:
            logger.info("Deployment %s already in Trapper (files organized in %s)", deployment.deployment_id, dest)
        yield {"type": "done", "dest_dir": str(dest)}

    return events()


def import_local_stream(source_dir: str, collection_dir: str, collection_name: str | None, deployment: DeploymentFields) -> Iterator[dict]:
    """Organizes source_dir's images under collection_dir/<deployment_id>,
    and records the collection's and deployment's own metadata as JSON —
    the "Local folder" destination, with no Trapper account involved.
    Events: the same "copy"/"done" shape as import_stream, with no
    "registering" step.

    Raises:
        DeploymentImportError: bad source/destination paths.
    """
    source = Path(source_dir).expanduser()
    collection = Path(collection_dir).expanduser()
    dest = collection / deployment.deployment_id
    check_paths(source, dest)

    def events() -> Iterator[dict]:
        local_folder_service.write_collection_metadata(collection, collection_name)
        yield from copy_folder(source, dest)
        local_folder_service.write_deployment_metadata(dest, deployment.model_dump())
        logger.info("Deployment %s organized locally in %s", deployment.deployment_id, dest)
        yield {"type": "done", "dest_dir": str(dest)}

    return events()
