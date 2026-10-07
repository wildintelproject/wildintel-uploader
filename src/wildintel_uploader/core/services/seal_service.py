"""The seal of a deployment: a file, beside its images, that says what was checked and keeps it tied to the content.

When a deployment is imported its images are validated and postvalidated (and, if asked, preprocessed), and seal.json
records, for the deployment and for each image, which checks it passed and which it did not:

    {"version", "sealed_at", "deployment_id",
     "deployment": {"sha256", "validations", "postvalidations", "preprocessing"},
     "images": [{"name", "original", "sha256", "source_sha1"?, "validations": {check: "ok" | problem},
                 "postvalidations": {check: "ok" | problem}}],
     "seal": sha256 of all of the above}

The checks run here, on the images the import read, so what the seal says is what the app found — not what a
browser reported. The seal protects against changes by mistake: verify() recomputes every hash and says if the
images or deployment.json are no longer what was sealed. It is not a signature — whoever edits the files on purpose
could seal them again.
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from wildintel_uploader.core import config, parallel
from wildintel_uploader.core.schemas.requests import DeploymentFields
from wildintel_uploader.core.services import deployment_import_service as dis
from wildintel_uploader.core.services import local_folder_service, statistics_service

logger = logging.getLogger(__name__)

SEAL_FILE = "seal.json"
VERSION = 1


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _seal_of(body: dict) -> str:
    """The hash of everything the seal says (all but the seal itself), however it was written."""
    text = json.dumps({k: v for k, v in body.items() if k != "seal"}, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _images_of(folder: Path) -> list[Path]:
    return sorted((p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in dis.IMAGE_EXTENSIONS), key=lambda p: dis._natural_key(p.relative_to(folder)))


def _problems(images: dict[str, list[str]]) -> dict[str, str]:
    """image -> its problems of one check, joined."""
    return {name: "; ".join(messages) for name, messages in images.items()}


def _per_image_validations(found: dict) -> dict[str, dict[str, str]]:
    """For each source image, the problem each image check found with it (a check with none is not listed)."""
    problems: dict[str, dict[str, dict[str, list[str]]]] = {}

    def add(check: str, path: str, message: str) -> None:
        problems.setdefault(check, {}).setdefault(path, []).append(message)

    for item in found.get("corrupted", []):
        add("corrupted", item["path"], item["error"])
    for item in found.get("sequence_issues", []):
        add("sequence", item["path_b"], f"dated before {item['path_a']}, which has a lower number")
    for group in found.get("duplicates", []):
        for name in group["files"]:
            add("duplicates", name, "same content as " + ", ".join(f for f in group["files"] if f != name))
    for field, info in found.get("exif_missing", {}).items():
        for name in info.get("files", []):
            add("exif", name, f"no {field}")
    return {check: _problems(images) for check, images in problems.items()}


def _checks(settings_section, names: frozenset[str] | tuple[str, ...]) -> frozenset[str]:
    return frozenset(name for name in names if getattr(settings_section, name))


def run_checks(source: Path, dest: Path, deployment: DeploymentFields) -> dict:
    """Runs the checks the settings turn on over the source images: {"validated": [...], "postvalidated": [...],
    "images": {source name: {"validations": {...}, "postvalidations": {...}}}, "deployment": {...}} — an image's check
    holds "ok" or what is wrong, the deployment's holds {"ok", "message"}."""
    settings = config.load_settings()
    post = settings.POSTVALIDATION
    image_checks = _checks(settings.VALIDATION, dis.IMAGE_CHECKS)
    deployment_checks = _checks(post, dis.DEPLOYMENT_CHECKS)
    stat_checks = _checks(post, statistics_service.STATISTIC_CHECKS)
    collections_dir, research_project_id = dest.parent.parent.parent, dest.parent.parent.name

    found = dis.validate_images(source, image_checks, detail=True)
    consistency = dis.validate_deployment_consistency(
        source, deployment, deployment_checks, collection_name=dest.parent.name, expected_location_id=deployment.location_id,
        tolerance_hours=post.tolerance_hours,
    )
    stats = statistics_service.statistical_checks(
        statistics_service.times_of_folder(source), collections_dir, research_project_id, deployment.deployment_id, stat_checks,
        sequence_gap_seconds=post.sequence_gap_seconds, min_revisions=post.min_revisions, method=post.similarity_method,
        tolerances={
            "image_count": post.image_count_tolerance, "sequence_count": post.sequence_count_tolerance,
            "sequence_length": post.sequence_length_tolerance,
        },
    ) if stat_checks else {}

    image_problems = _per_image_validations(found)
    out_of_range = {item["path"]: f"{item['date']} is out of the range for the {item['rule']} image ({item['expected']})" for item in consistency.get("out_of_range", [])}
    mismatches = {item["path"]: f"camera {item['detected']} is not the deployment's" for item in consistency.get("camera_mismatches", [])}

    images: dict[str, dict] = {}
    for path in _images_of(source):
        name = str(path.relative_to(source))
        validations = {check: image_problems.get(check, {}).get(name, "ok") for check in image_checks & {"corrupted", "sequence", "duplicates", "exif"}}
        postvalidations = {}
        if "time_range" in deployment_checks:
            postvalidations["time_range"] = out_of_range.get(name, "ok")
        if "camera" in deployment_checks:
            postvalidations["camera"] = mismatches.get(name, "ok")
        images[name] = {"validations": validations, "postvalidations": postvalidations}

    on_deployment: dict[str, dict] = {"validations": {}, "postvalidations": {}}
    if "structure" in image_checks:
        folders = found.get("subdirectories", [])
        on_deployment["validations"]["structure"] = {"ok": not folders, "message": "all the images are in one folder" if not folders else f"images in subfolders: {', '.join(folders)}"}
    if "camera" in image_checks:
        cameras = found.get("cameras", [])
        on_deployment["validations"]["camera"] = {"ok": len(cameras) <= 1, "message": f"{len(cameras)} camera(s), {found.get('cameras_without_info', 0)} image(s) without camera information"}
    for check in dis.DEPLOYMENT_CHECKS & deployment_checks:
        if isinstance(consistency.get(check), dict):
            on_deployment["postvalidations"][check] = consistency[check]
    for check, result in stats.items():
        on_deployment["postvalidations"][check] = {"ok": bool(result.get("ok")), "message": result.get("message", "")}
    return {"validated": sorted(image_checks), "postvalidated": sorted(deployment_checks | stat_checks), "images": images, "deployment": on_deployment}


def seal(
    source: Path, dest: Path, deployment: DeploymentFields, *,
    originals: dict[str, str] | None = None, source_hashes: dict[str, str] | None = None, preprocessing: dict | None = None,
    recovered: bool = False,
) -> dict:
    """Checks the source images, then writes dest/seal.json for what the import left in dest.

    originals maps each image of dest to the source image it came from (the same name when it is None) — how a
    preprocessed, renamed image gets the checks of its original. source_hashes holds the SHA-1 of those originals,
    and preprocessing the options the images were processed with (None when they were only copied). recovered says the
    seal was written by a repair, from what the folder held, not by the import. Returns what was written."""
    checked = run_checks(source, dest, deployment)
    files = _images_of(dest)
    names = [str(p.relative_to(dest)) for p in files]
    hashes = parallel.pmap(_sha256, files)
    entries = []
    for name, digest in zip(names, hashes):
        original = (originals or {}).get(name, name)
        entry = {"name": name, "original": original, "sha256": digest, **checked["images"].get(original, {"validations": {}, "postvalidations": {}})}
        if source_hashes and original in source_hashes:
            entry["source_sha1"] = source_hashes[original]
        entries.append(entry)
    body = {
        "version": VERSION, "sealed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "deployment_id": deployment.deployment_id,
        "deployment": {
            "sha256": _sha256(dest / local_folder_service.DEPLOYMENT_METADATA_FILE), "validated": checked["validated"],
            "postvalidated": checked["postvalidated"], "preprocessing": preprocessing, **checked["deployment"],
        },
        "images": entries,
    }
    if recovered:
        body["recovered"] = {"at": body["sealed_at"], "from": "the contents of the deployment's own folder"}
    body["seal"] = _seal_of(body)
    (dest / SEAL_FILE).write_text(json.dumps(body, indent=2, ensure_ascii=False), encoding="utf-8")
    return body


def verify(dest: Path) -> dict:
    """Whether dest is still what its seal says: {"status": "none" | "valid" | "broken", "changed", "missing", "added",
    "deployment_changed", "seal_changed"} — the lists name the images that differ. "none" is a deployment never sealed."""
    path = dest / SEAL_FILE
    if not path.is_file():
        return {"status": "none", "changed": [], "missing": [], "added": [], "deployment_changed": False, "seal_changed": False}
    try:
        body = json.loads(path.read_text(encoding="utf-8"))
        recorded = {e["name"]: e["sha256"] for e in body["images"]}
        deployment_hash = body["deployment"]["sha256"]
        seal_changed = _seal_of(body) != body["seal"]
    except (json.JSONDecodeError, OSError, KeyError, TypeError):
        return {"status": "broken", "changed": [], "missing": [], "added": [], "deployment_changed": False, "seal_changed": True}
    files = {str(p.relative_to(dest)): p for p in _images_of(dest)}
    present = [name for name in recorded if name in files]
    digests = dict(zip(present, parallel.pmap(_sha256, [files[n] for n in present])))
    changed = sorted(n for n in present if digests[n] != recorded[n])
    missing = sorted(n for n in recorded if n not in files)
    added = sorted(n for n in files if n not in recorded)
    metadata = dest / local_folder_service.DEPLOYMENT_METADATA_FILE
    deployment_changed = not metadata.is_file() or _sha256(metadata) != deployment_hash
    broken = bool(changed or missing or added or deployment_changed or seal_changed)
    return {"status": "broken" if broken else "valid", "changed": changed, "missing": missing, "added": added, "deployment_changed": deployment_changed, "seal_changed": seal_changed}
