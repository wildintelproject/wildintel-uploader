"""Repairing a deployment kept in the collections folder — plain Python: its metadata files, when they are gone or its seal no longer matches,
are written again from what the folder itself holds.

A deployment is **valid** when its seal.json still matches it; anything else is not. Repairing it reads the capture date of every image (the
camera's wall clock, from its EXIF) and its camera; takes the deployment's period from the collection's FileTimestampLog.csv if an old one has a
row of it — the log always prevails over what the images say — else from the deployment.json that is left, else from the images; writes
deployment.json, preprocessing.json and images.json as the images are; and seals it again. What can't be known is left as it was or empty: the
original name of a renamed image, and the options it was preprocessed with, unless a preprocessing.json that is left says so. A deployment synced
from TRAPPER is not touched."""
from __future__ import annotations

import re
from dataclasses import fields
from datetime import datetime

from wildintel_uploader.modules.deployments.domain.models import DeploymentImportError
from wildintel_uploader.modules.deployments.domain.naming import DEPLOYMENT_METADATA_FILE, IMAGES_FILE
from wildintel_uploader.modules.deployments.domain.seal import SEAL_FILE
from wildintel_uploader.modules.preprocessing.domain import models as pre

METADATA_FILES = (DEPLOYMENT_METADATA_FILE, IMAGES_FILE, pre.PREPROCESSING_LOG_FILE, SEAL_FILE)
_COLLECTION = re.compile(r"^R\d{4}(_.+)?$")
_DEPLOYMENT = re.compile(r"^R\d{4}-.+$")
STATUS = {"valid": "valid", "broken": "broken", "none": "unsealed"}


class RepairError(DeploymentImportError):
    """A deployment that can't be inspected or repaired — and why."""


def is_collection(name: str) -> bool:
    return bool(_COLLECTION.match(name))


def is_deployment(name: str) -> bool:
    return bool(_DEPLOYMENT.match(name))


def check_names(collection: str, deployment_id: str | None = None) -> None:
    """Raises RepairError when they are not a collection's name and a deployment's id."""
    if not is_collection(collection):
        raise RepairError(f"'{collection}' isn't a collection's name.")
    if deployment_id is not None and not is_deployment(deployment_id):
        raise RepairError(f"'{deployment_id}' isn't a deployment's id.")


def zone(name: str):
    """A timezone — an unknown one is a RepairError's kind of error."""
    try:
        return pre.zone_of(name)
    except pre.PreprocessingError as exc:
        raise DeploymentImportError(str(exc)) from exc


def inspection(deployment_id: str, files: dict[str, str], images: int, log: str, synced: bool, seal: dict | None) -> dict:
    """The state of a deployment: {"deployment_id", "status": "valid" | "broken" | "unsealed" | "synced", "seal", "files": {name: "ok" | "missing"
    | "unreadable"}, "images", "log": "row" | "no row" | "no log" | <what is wrong with it>, "problems"}. Valid is what its seal says — nothing
    else decides it."""
    if synced:
        return {"deployment_id": deployment_id, "status": "synced", "seal": None, "files": files, "images": images, "log": log,
                "problems": ["It was synced from TRAPPER: what TRAPPER holds is not modified here."]}
    problems = [f"{name} is {state}" for name, state in files.items() if state != "ok" and not (name == SEAL_FILE and state == "missing")]
    if seal["status"] == "none":
        problems.append("It has no seal: its images were never sealed.")
    if seal["status"] == "broken":
        for key, text in (("changed", "image(s) changed since they were sealed"), ("missing", "sealed image(s) missing"), ("added", "image(s) added since it was sealed")):
            if seal[key]:
                problems.append(f"{len(seal[key])} {text}")
        if seal["deployment_changed"]:
            problems.append("deployment.json is not what was sealed")
        if seal["seal_changed"]:
            problems.append("seal.json itself was changed")
    if log not in ("row", "no row", "no log"):
        problems.append(log)   # a log that is there and can't be read; having none is not a problem (#213)
    if not images:
        problems.append("There are no images in the folder.")
    return {"deployment_id": deployment_id, "status": STATUS[seal["status"]], "seal": seal, "files": files, "images": images, "log": log, "problems": problems}


def options_of(defaults: dict, old: dict | None, location_time: dict, name_zone: str | None) -> pre.PreprocessOptions:
    """The options the images were preprocessed with: the ones a preprocessing.json that is left says, else the settings' (`defaults`) — with
    the location's timezone and summer-time setting — since nothing else says."""
    names = {f.name for f in fields(pre.PreprocessOptions)}
    base = {k: v for k, v in defaults.items() if k in names}
    base.update({k: v for k, v in location_time.items() if k in ("timezone", "ignore_dst")})
    if isinstance(old, dict) and isinstance(old.get("options"), dict):
        base.update({k: v for k, v in old["options"].items() if k in names})
    if not base.get("timezone"):
        base["timezone"] = name_zone or ""
    if not base["timezone"]:
        raise RepairError("There is no timezone to read the capture dates in: set it in the location's time settings first.")
    zone(base["timezone"])
    return pre.PreprocessOptions(**base)


def row_times(row: dict) -> tuple[datetime, datetime]:
    try:
        return (datetime.strptime(f"{row['StartDate']} {row['StartTime']}", "%Y:%m:%d %H:%M:%S"),
                datetime.strptime(f"{row['EndDate']} {row['EndTime']}", "%Y:%m:%d %H:%M:%S"))
    except ValueError as exc:
        raise RepairError(f"The timestamp log's row of this deployment can't be read: {exc}") from exc


def period(deployment_id: str, row: dict | None, old_deployment: dict | None, computed: tuple[datetime, datetime] | None) -> tuple[datetime, datetime, str]:
    """When the deployment was, and what says so: the timestamp log's row prevails over the images, else the deployment.json that was left,
    else the images.

    Raises:
        RepairError: nothing says it, or what says it ends before it starts."""
    start = end = None
    if row:
        start, end = row_times(row)
        note = "the timestamp log says so"
        if computed and (computed[0] < start.replace(microsecond=0) or computed[1] > end):
            note += f" — its images were taken {computed[0]:%Y-%m-%d %H:%M:%S} → {computed[1]:%Y-%m-%d %H:%M:%S}, and the log prevails"
    elif old_deployment and old_deployment.get("start_date") and old_deployment.get("end_date"):
        try:
            start, end = (datetime.fromisoformat(old_deployment[k]).replace(tzinfo=None) for k in ("start_date", "end_date"))
            note = "the deployment.json that was left says so"
        except ValueError:
            start = end = None
    if start is None or end is None:
        if not computed:
            raise RepairError("It has no row in the timestamp log, no dates in its deployment.json and no images to read them from.")
        (start, end), note = computed, "read from its images"
    if end <= start:
        raise RepairError(f"The period of {deployment_id} is not valid: it ends ({end}) before it starts ({start}).")
    return start, end, note


def deployment_record(deployment_id: str, location_id: str | None, location: dict, models: set, camera_ids: set, old: dict | None,
                      start: str, end: str) -> dict:
    """deployment.json rebuilt: what is left of it prevails over the location's details and the camera the images say, with the period."""
    found = {"deployment_id": deployment_id, "location_id": location_id, "location_name": location.get("name"), "latitude": location.get("latitude"),
             "longitude": location.get("longitude"), "coordinate_uncertainty": location.get("coordinate_uncertainty"),
             "camera_model": next(iter(models)) if len(models) == 1 else None, "camera_id": next(iter(camera_ids)) if len(camera_ids) == 1 else None}
    merged = {**{k: v for k, v in found.items() if v is not None}, **{k: v for k, v in (old or {}).items() if v is not None}}
    return {**merged, "deployment_id": deployment_id, "start_date": start, "end_date": end}


def what_changed(old: dict | None, body: dict) -> str:
    return "rebuilt" if old is None else "updated: " + ", ".join(sorted(k for k in body if (old or {}).get(k) != body[k]))


def preprocessing_problems(deployment_id: str, records: list[dict], options: pre.PreprocessOptions, old: dict[str, dict],
                           identified: dict[str, bool] | None) -> dict[str, dict[str, str]]:
    """The checks of the preprocessing the folder can answer: check -> {image: what is wrong}. Names: <DEPLOYMENT>__<YYYYMMDD>_<n>.<EXT> with the
    day of the capture date and a number once each; size: not wider than the width asked for; metadata: the XMP identifier is there
    (`identified`, when ExifTool could say); hash: the file is the one that was preprocessed."""
    problems: dict[str, dict[str, str]] = {"preprocessing_names": {}, "preprocessing_size": {}, "preprocessing_metadata": {}, "preprocessing_hash": {}}
    pattern = re.compile(rf"^{re.escape(deployment_id.upper())}__(\d{{8}})_(\d+)(\.[A-Z]+)$")
    numbers: dict[str, list[str]] = {}
    for r in records:
        match = pattern.match(r["name"].replace("\\", "/").rsplit("/", 1)[-1])
        if not match:
            problems["preprocessing_names"][r["name"]] = f"is not named <{deployment_id.upper()}>__<YYYYMMDD>_<n>.<EXT>"
            continue
        day = datetime.fromisoformat(r["date"]).strftime("%Y%m%d")
        if match.group(1) != day:
            problems["preprocessing_names"][r["name"]] = f"its name says {match.group(1)} and its capture date is {day}"
        numbers.setdefault(match.group(2), []).append(r["name"])
    for number, names in numbers.items():
        if len(names) > 1:
            for name in names:
                problems["preprocessing_names"][name] = f"the number {number} is also in {', '.join(n for n in names if n != name)}"
    if options.resize:
        for r in records:
            width = r.get("width")
            if width and width > options.resize_width:
                problems["preprocessing_size"][r["name"]] = f"is {width} px wide, more than the {options.resize_width} px asked for"
    if options.metadata and identified:
        for r in records:
            if not identified.get(r["name"]):
                problems["preprocessing_metadata"][r["name"]] = "has no WildINTEL identifier in its XMP metadata"
    for r in records:
        before = old.get(r["name"])
        if before and before.get("final_hash") and before["final_hash"] != r["final_hash"]:
            problems["preprocessing_hash"][r["name"]] = "is not the file that was preprocessed (its hash changed)"
    return problems
