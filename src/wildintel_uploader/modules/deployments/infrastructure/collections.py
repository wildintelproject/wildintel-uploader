"""How the collections folder holds the deployments: <collections folder>/<research project>/<collection>/<deployment id>, with collection.json,
deployment.json and images.json beside the images, the logs of a collection (its FileTimestampLog and FieldworkLog), and what was imported before
into a research project."""
from __future__ import annotations

import csv
import json
from pathlib import Path

from wildintel_uploader.modules.deployments.domain.naming import COLLECTION_METADATA_FILE, DEPLOYMENT_METADATA_FILE, IMAGES_FILE  # noqa: F401
from wildintel_uploader.shared import storage

LocalFolderError = storage.StorageError   # what can't be read or kept in the collections folder







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


from wildintel_uploader.modules.deployments.domain.imports import TIMESTAMP_LOG_SUFFIX  # noqa: E402 — the domain's


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
