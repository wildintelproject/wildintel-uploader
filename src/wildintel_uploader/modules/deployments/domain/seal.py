"""The seal of a deployment — plain Python: what it says, and whether a deployment is still what it says.

When a deployment is imported its images are validated and postvalidated (and, if asked, preprocessed), and seal.json records, for the
deployment and for each image, which checks it passed and which it did not:

    {"version", "sealed_at", "deployment_id",
     "deployment": {"sha256", "validations", "postvalidations", "preprocessing"},
     "images": [{"name", "original", "sha256", "source_sha1"?, "validations": {check: "ok" | problem},
                 "postvalidations": {check: "ok" | problem}}],
     "seal": sha256 of all of the above}

The seal protects against changes by mistake: verifying it recomputes every hash and says if the images or deployment.json are no longer what
was sealed. It is not a signature — whoever edits the files on purpose could seal them again."""
from __future__ import annotations

import hashlib
import json

SEAL_FILE = "seal.json"
VERSION = 1
IMAGE_CHECKS = frozenset({"corrupted", "sequence", "duplicates", "exif"})   # the checks of the images a seal says of each one
NOT_SEALED = {"status": "none", "changed": [], "missing": [], "added": [], "deployment_changed": False, "seal_changed": False}


def seal_of(body: dict) -> str:
    """The hash of everything the seal says (all but the seal itself), however it was written."""
    text = json.dumps({k: v for k, v in body.items() if k != "seal"}, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def turned_on(section: object, names) -> frozenset[str]:
    """The checks of those names a section of the settings turns on."""
    return frozenset(name for name in names if getattr(section, name))


def per_image_validations(found: dict) -> dict[str, dict[str, str]]:
    """For each source image, the problem each image check found with it (a check with none is not listed): check -> {image: problems}."""
    problems: dict[str, dict[str, list[str]]] = {}

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
            add("exif", name, f"no {info.get('label') or field}")
    return {check: {name: "; ".join(messages) for name, messages in images.items()} for check, images in problems.items()}


def checked(images: list[str], found: dict, consistency: dict, image_checks: frozenset[str], deployment_checks: frozenset[str],
            stat_checks: frozenset[str]) -> dict:
    """What the checks found, as the seal says it: {"validated", "postvalidated", "images": {source name: {"validations", "postvalidations"}},
    "deployment": {"validations", "postvalidations"}} — an image's check holds "ok" or what is wrong, the deployment's {"ok", "message"}."""
    image_problems = per_image_validations(found)
    out_of_range = {i["path"]: f"{i['date']} is out of the range for the {i['rule']} image ({i['expected']})" for i in consistency.get("out_of_range", [])}
    mismatches = {i["path"]: f"camera {i['detected']} is not the deployment's" for i in consistency.get("camera_mismatches", [])}
    per_image: dict[str, dict] = {}
    for name in images:
        validations = {check: image_problems.get(check, {}).get(name, "ok") for check in image_checks & IMAGE_CHECKS}
        postvalidations = {}
        if "time_range" in deployment_checks:
            postvalidations["time_range"] = out_of_range.get(name, "ok")
        if "camera" in deployment_checks:
            postvalidations["camera"] = mismatches.get(name, "ok")
        per_image[name] = {"validations": validations, "postvalidations": postvalidations}
    on_deployment: dict[str, dict] = {"validations": {}, "postvalidations": {}}
    if "structure" in image_checks:
        folders = found.get("subdirectories", [])
        on_deployment["validations"]["structure"] = {"ok": not folders, "message": "all the images are in one folder" if not folders else f"images in subfolders: {', '.join(folders)}"}
    if "camera" in image_checks:
        cameras = found.get("cameras", [])
        on_deployment["validations"]["camera"] = {"ok": len(cameras) <= 1, "message": f"{len(cameras)} camera(s), {found.get('cameras_without_info', 0)} image(s) without camera information"}
    for check in deployment_checks:
        if isinstance(consistency.get(check), dict):
            on_deployment["postvalidations"][check] = consistency[check]
    for check in stat_checks:
        if check in consistency:
            on_deployment["postvalidations"][check] = {"ok": bool(consistency[check].get("ok")), "message": consistency[check].get("message", "")}
    return {"validated": sorted(image_checks), "postvalidated": sorted(deployment_checks | stat_checks), "images": per_image, "deployment": on_deployment}


def body(deployment_id: str, sealed_at: str, metadata_sha256: str, checks: dict, images: list[tuple[str, str]], *, originals: dict[str, str] | None,
         source_hashes: dict[str, str] | None, preprocessing: dict | None, recovered: bool) -> dict:
    """The seal of a deployment: `images` are (name, sha256) of what it holds; `originals` maps each to the source image it came from (the same
    name when it is None) — how a preprocessed, renamed image gets the checks of its original —; `source_hashes` the SHA-1 of those originals;
    `recovered` says a repair wrote it, from what the folder held."""
    entries = []
    for name, digest in images:
        original = (originals or {}).get(name, name)
        entry = {"name": name, "original": original, "sha256": digest, **checks["images"].get(original, {"validations": {}, "postvalidations": {}})}
        if source_hashes and original in source_hashes:
            entry["source_sha1"] = source_hashes[original]
        entries.append(entry)
    out = {"version": VERSION, "sealed_at": sealed_at, "deployment_id": deployment_id,
           "deployment": {"sha256": metadata_sha256, "validated": checks["validated"], "postvalidated": checks["postvalidated"],
                          "preprocessing": preprocessing, **checks["deployment"]},
           "images": entries}
    if recovered:
        out["recovered"] = {"at": sealed_at, "from": "the contents of the deployment's own folder"}
    out["seal"] = seal_of(out)
    return out


def recorded(seal: dict) -> tuple[dict[str, str], str, bool]:
    """What a seal recorded — {image: sha256}, the hash of deployment.json — and whether the seal itself was changed. KeyError or TypeError when
    it is not a seal."""
    return {e["name"]: e["sha256"] for e in seal["images"]}, seal["deployment"]["sha256"], seal_of(seal) != seal["seal"]


def verdict(images: dict[str, str], now: dict[str, str], present: list[str], deployment_changed: bool, seal_changed: bool) -> dict:
    """Whether a deployment is still what its seal says — `images` as sealed, `now` the hashes of those still there, `present` every image there
    is —: {"status": "valid" | "broken", "changed", "missing", "added", "deployment_changed", "seal_changed"}."""
    changed = sorted(n for n in now if now[n] != images[n])
    missing = sorted(n for n in images if n not in present)
    added = sorted(n for n in present if n not in images)
    broken = bool(changed or missing or added or deployment_changed or seal_changed)
    return {"status": "broken" if broken else "valid", "changed": changed, "missing": missing, "added": added, "deployment_changed": deployment_changed,
            "seal_changed": seal_changed}
