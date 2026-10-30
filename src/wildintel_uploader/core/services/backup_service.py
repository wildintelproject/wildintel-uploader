"""Backups: the settings and the data of a research project — its locations, cameras, SD cards, visits and deployments, with or without the images — in one .zip
that says what it holds (manifest.json), and the restoration of what is picked from it.

The zip holds:

  manifest.json                                what it holds, of which research project, when, and by which version of the app
  settings.json                                the global settings, with no passwords or secrets and none of the folders of this computer
  project/research_project.json, locations.json, cameras.json, sd_cards.json   what the research project is
  project/visits.json                          the list of visits
  deployments/<collection>/<deployment>/...    what a deployment keeps — with its images only when they were asked for
  deployments/<collection>/<name>              the files of a collection (its collection.json and its logs)

Restoring never overwrites what is there unless it is asked to; and what is retired stays retired (a retired location, camera or SD card is retired for good).
"""
from __future__ import annotations

import json
import os
import re
import tempfile
import zipfile
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from wildintel_uploader.core import config
from wildintel_uploader.core.services import local_folder_service

FORMAT = "wildintel-uploader-backup"
VERSION = 1
MANIFEST = "manifest.json"
SETTINGS = "settings.json"
PROJECT_FILES = (
    local_folder_service.RESEARCH_PROJECT_METADATA_FILE, local_folder_service.LOCATIONS_FILE, local_folder_service.CAMERAS_FILE, local_folder_service.SD_CARDS_FILE,
)
VISITS = local_folder_service.VISITS_FILE
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".gif", ".webp", ".mp4", ".avi", ".mov", ".mkv", ".m4v"}
_COLLECTION = re.compile(r"^R\d+$", re.IGNORECASE)
# what a settings backup does not hold: the secrets, and the folders of this computer
_SECRETS = (("TRAPPER", "user_password"), ("EPICOLLECT5", "client_secret"), ("AGOUTI", "api_key"))


class BackupError(ValueError):
    """The backup cannot be made, read or restored — the message says why, for the person."""


def _is_image(name: str) -> bool:
    return Path(name).suffix.lower() in IMAGE_EXTENSIONS


def _write_json(path: Path, data) -> None:
    """Put in place at once: a file is never left half written."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def _read(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


# ── what there is to back up ──────────────────────────────────────────────────────────────────────────────────────────────────

def _walk(folder: Path) -> list[Path]:
    return sorted(p for p in folder.rglob("*") if p.is_file())


def describe_project(root: Path, research_project_id: str) -> dict:
    """What a research project has that can be put in a backup: how many locations, cameras, SD cards and visits, and each deployment of each collection with its
    files and how many bytes they are — those that are images apart.

    Raises:
        BackupError: the research project is not kept in the collections folder.
    """
    try:
        local_folder_service.require_research_project(root, research_project_id)
    except local_folder_service.LocalFolderError as exc:
        raise BackupError(str(exc)) from exc
    pdir = local_folder_service.project_dir(root, research_project_id)
    collections = []
    for collection in sorted((c for c in pdir.iterdir() if c.is_dir() and _COLLECTION.match(c.name)), key=lambda c: c.name, reverse=True):
        deployments = []
        for folder in sorted(d for d in collection.iterdir() if d.is_dir()):
            files = _walk(folder)
            images = [f for f in files if _is_image(f.name)]
            deployments.append({
                "id": folder.name, "files": len(files), "bytes": sum(f.stat().st_size for f in files),
                "images": len(images), "image_bytes": sum(f.stat().st_size for f in images),
            })
        collections.append({"name": collection.name, "deployments": deployments})
    return {
        "research_project_id": research_project_id,
        "locations": len(local_folder_service.list_locations(root, research_project_id)),
        "cameras": len(local_folder_service.list_field_items(root, research_project_id, "cameras")),
        "sd_cards": len(local_folder_service.list_field_items(root, research_project_id, "sd_cards")),
        "visits": len(local_folder_service._raw_visits(root, research_project_id)),
        "collections": collections,
    }


def settings_snapshot(settings: config.Settings | None = None) -> dict:
    """The global settings as they go in a backup: without passwords or secrets, and without the folders of this computer — nor the cameras and the SD cards, which
    belong to their research projects."""
    data = (settings or config.load_settings()).model_dump(mode="json")
    for section, field in _SECRETS:
        data[section][field] = None
    data.pop("DATA", None)
    data["FIELDWORK"]["cameras"] = []
    data["FIELDWORK"]["sd_cards"] = []
    return data


# ── making a backup ───────────────────────────────────────────────────────────────────────────────────────────────────────────

def create_backup(
    root: Path, dest_dir: Path, *, settings: bool, research_project_id: str | None, project_files: bool, visits: bool, deployments: list[str], images: bool, app_version: str,
) -> Iterator[dict]:
    """Makes the backup in `dest_dir`: yields {"type": "step"|"file"|"done"} events — the last has the `path` of the .zip, its `bytes` and the `manifest`.

    Raises:
        BackupError: the folder is not there, nothing was asked for, or the research project or a deployment is not there.
    """
    if not dest_dir.is_dir():
        raise BackupError(f"The folder {dest_dir} is not there.")
    wants_project = project_files or visits or bool(deployments)
    if not settings and not wants_project:
        raise BackupError("Nothing was chosen to put in the backup.")
    if wants_project and not research_project_id:
        raise BackupError("Choose the research project the backup is of.")
    yield {"type": "step", "message": "Looking at what is going in…"}
    entries: list[tuple[str, Path | None, object | None]] = []   # (name in the zip, file on disk, or the data to write)
    scope: dict = {"settings": settings, "research_project": research_project_id if wants_project else None, "project_files": project_files, "visits": visits, "images": images, "deployments": []}
    if settings:
        entries.append((SETTINGS, None, settings_snapshot()))
    counts: dict = {}
    if wants_project:
        info = describe_project(root, research_project_id)  # type: ignore[arg-type]
        pdir = local_folder_service.project_dir(root, research_project_id)  # type: ignore[arg-type]
        if project_files:
            for name in PROJECT_FILES:
                if (pdir / name).is_file():
                    entries.append((f"project/{name}", pdir / name, None))
            counts.update({"locations": info["locations"], "cameras": info["cameras"], "sd_cards": info["sd_cards"]})
        if visits and (pdir / VISITS).is_file():
            entries.append((f"project/{VISITS}", pdir / VISITS, None))
            counts["visits"] = info["visits"]
        done_collections: set[str] = set()
        for deployment_id in deployments:
            collection = deployment_id.split("-", 1)[0].upper()
            folder = pdir / collection / deployment_id
            if not folder.is_dir():
                raise BackupError(f"The deployment {deployment_id} is not in {research_project_id}.")
            kept = 0
            for path in _walk(folder):
                if not images and _is_image(path.name):
                    continue
                entries.append((f"deployments/{collection}/{deployment_id}/{path.relative_to(folder).as_posix()}", path, None))
                kept += 1
            scope["deployments"].append({"id": deployment_id, "collection": collection, "files": kept, "images": images})
            if collection not in done_collections:
                done_collections.add(collection)
                for extra in sorted(p for p in (pdir / collection).iterdir() if p.is_file()):
                    entries.append((f"deployments/{collection}/{extra.name}", extra, None))
    manifest = {
        "format": FORMAT, "version": VERSION, "app_version": app_version, "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "scope": scope, "counts": counts, "secrets_included": False,
    }
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = dest_dir / f"wildintel-backup_{research_project_id if wants_project else 'settings'}_{stamp}.zip"
    fd, tmp = tempfile.mkstemp(dir=dest_dir, prefix=".backup.", suffix=".tmp")
    os.close(fd)
    try:
        with zipfile.ZipFile(tmp, "w") as zf:
            zf.writestr(MANIFEST, json.dumps(manifest, indent=2, ensure_ascii=False), compress_type=zipfile.ZIP_DEFLATED)
            total = len(entries)
            for index, (name, path, data) in enumerate(entries, start=1):
                if path is None:
                    zf.writestr(name, json.dumps(data, indent=2, ensure_ascii=False), compress_type=zipfile.ZIP_DEFLATED)
                else:  # an image is already compressed: it is stored as it is
                    zf.write(path, name, compress_type=zipfile.ZIP_STORED if _is_image(name) else zipfile.ZIP_DEFLATED)
                yield {"type": "file", "index": index, "total": total, "name": name}
        os.replace(tmp, target)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    yield {"type": "done", "path": str(target), "bytes": target.stat().st_size, "files": len(entries) + 1, "manifest": manifest}


# ── reading a backup ──────────────────────────────────────────────────────────────────────────────────────────────────────────

def _open(path: Path) -> zipfile.ZipFile:
    if not path.is_file():
        raise BackupError(f"The file {path} is not there.")
    try:
        zf = zipfile.ZipFile(path)
    except zipfile.BadZipFile as exc:
        raise BackupError("That file is not a backup: it is not a .zip.") from exc
    for name in zf.namelist():
        parts = PurePosixPath(name).parts
        if name.startswith(("/", "\\")) or ".." in parts or (len(name) > 1 and name[1] == ":"):
            zf.close()
            raise BackupError("That backup has files with a path that goes out of it: it is not restored.")
    return zf


def _manifest(zf: zipfile.ZipFile) -> dict:
    try:
        manifest = json.loads(zf.read(MANIFEST))
    except (KeyError, json.JSONDecodeError) as exc:
        raise BackupError("That .zip is not a backup of this app: it has no manifest.") from exc
    if not isinstance(manifest, dict) or manifest.get("format") != FORMAT:
        raise BackupError("That .zip is not a backup of this app.")
    if int(manifest.get("version", 0)) > VERSION:
        raise BackupError("That backup was made by a newer version of the app: update it to restore it.")
    return manifest


def _key(visit: dict) -> tuple:
    return (str(visit.get("location_id", "")).lower(), visit.get("when") or f"{visit.get('date')}T{visit.get('time')}")


def read_backup(root: Path, path: Path) -> dict:
    """What a backup holds — its manifest — and what of it is already here: the research project, each deployment, and how many of its visits (the same site and
    instant) are already kept.

    Raises:
        BackupError: the file is not a backup, or one of this app's newer versions made it.
    """
    with _open(path) as zf:
        manifest = _manifest(zf)
        names = set(zf.namelist())
        scope = manifest.get("scope", {})
        project = scope.get("research_project")
        here: dict = {"project": False, "deployments": {}, "visits": {"in_backup": 0, "already": 0}}
        if project:
            try:
                pdir = local_folder_service.project_dir(root, project)
            except local_folder_service.LocalFolderError as exc:
                raise BackupError(str(exc)) from exc
            here["project"] = (pdir / local_folder_service.RESEARCH_PROJECT_METADATA_FILE).is_file()
            for d in scope.get("deployments", []):
                folder = pdir / d["collection"] / d["id"]
                here["deployments"][d["id"]] = folder.is_dir() and any(folder.iterdir())
            if f"project/{VISITS}" in names:
                backed = json.loads(zf.read(f"project/{VISITS}"))
                mine = {_key(v) for v in local_folder_service._raw_visits(root, project)} if here["project"] else set()
                here["visits"] = {"in_backup": len(backed), "already": sum(_key(v) in mine for v in backed)}
        has_images = {d["id"]: any(n.startswith(f"deployments/{d['collection']}/{d['id']}/") and _is_image(n) for n in names) for d in scope.get("deployments", [])}
    return {"manifest": manifest, "here": here, "has_images": has_images}


# ── restoring ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────

def _merge(current: list[dict], backed: list[dict], key, *, replace: bool) -> tuple[list[dict], int, int, int]:
    """The list kept with what the backup adds: what is there stays unless `replace` says the backup's wins — except what is retired, which is retired for good.
    Returns the list and how many were added, replaced and left as they were."""
    out = list(current)
    index = {key(item): i for i, item in enumerate(out)}
    added = replaced = skipped = 0
    for item in backed:
        k = key(item)
        if k not in index:
            index[k] = len(out)
            out.append(item)
            added += 1
        elif replace and out[index[k]].get("status") != "retired":
            out[index[k]] = item
            replaced += 1
        else:
            skipped += 1
    return out, added, replaced, skipped


def restore_backup(
    root: Path, path: Path, *, settings: bool, project_files: bool, visits: bool, deployments: list[str], images: bool, replace: bool,
) -> Iterator[dict]:
    """Restores what is picked of a backup: yields {"type": "step"|"file"|"done"} events — the last has a `summary` of what was added, replaced and left as it was.

    Raises:
        BackupError: the backup cannot be read, or what is asked for is not in it, or the research project is not here and its data is not being restored.
    """
    with _open(path) as zf:
        manifest = _manifest(zf)
        scope = manifest.get("scope", {})
        names = set(zf.namelist())
        project = scope.get("research_project")
        summary: dict = {"settings": False, "project_files": {}, "visits": {}, "deployments": {"restored": [], "skipped": []}, "files": 0}
        if settings and SETTINGS not in names:
            raise BackupError("That backup holds no settings.")
        wants_project = project_files or visits or bool(deployments)
        if wants_project and not project:
            raise BackupError("That backup holds no research project.")
        pdir = local_folder_service.project_dir(root, project) if wants_project else None
        if wants_project:
            for d in deployments:
                if not any(x["id"] == d for x in scope.get("deployments", [])):
                    raise BackupError(f"The deployment {d} is not in that backup.")
            if not (pdir / local_folder_service.RESEARCH_PROJECT_METADATA_FILE).is_file() and not (project_files and f"project/{local_folder_service.RESEARCH_PROJECT_METADATA_FILE}" in names):
                raise BackupError(f"The research project {project} is not here: restore its data too.")  # type: ignore[arg-type]

        if wants_project and project_files:
            yield {"type": "step", "message": f"Restoring the data of {project}…"}
            rp_name = local_folder_service.RESEARCH_PROJECT_METADATA_FILE
            if f"project/{rp_name}" in names:
                target = pdir / rp_name  # type: ignore[operator]
                if replace or not target.is_file():
                    _write_json(target, json.loads(zf.read(f"project/{rp_name}")))
                    summary["project_files"]["research_project"] = "written"
                else:
                    summary["project_files"]["research_project"] = "kept"
            for name, label, key in ((local_folder_service.LOCATIONS_FILE, "locations", lambda i: str(i.get("location_id", "")).lower()),
                                     (local_folder_service.CAMERAS_FILE, "cameras", lambda i: str(i.get("label") or i.get("camera_id") or "").lower()),
                                     (local_folder_service.SD_CARDS_FILE, "sd_cards", lambda i: str(i.get("label", "")).lower())):
                if f"project/{name}" not in names:
                    continue
                backed = [i for i in json.loads(zf.read(f"project/{name}")) if isinstance(i, dict)]
                current = [i for i in _read(pdir / name, []) if isinstance(i, dict)]  # type: ignore[operator]
                merged, added, replaced, skipped = _merge(current, backed, key, replace=replace)
                _write_json(pdir / name, merged)  # type: ignore[operator]
                summary["project_files"][label] = {"added": added, "replaced": replaced, "kept": skipped}
        if wants_project and visits:
            yield {"type": "step", "message": f"Restoring the visits of {project}…"}
            if f"project/{VISITS}" not in names:
                raise BackupError("That backup holds no visits.")
            backed = [v for v in json.loads(zf.read(f"project/{VISITS}")) if isinstance(v, dict)]
            current = local_folder_service._raw_visits(root, project)  # type: ignore[arg-type]
            merged, added, replaced, skipped = _merge(current, backed, _key, replace=replace)
            _write_json(pdir / VISITS, merged)  # type: ignore[operator]
            summary["visits"] = {"added": added, "replaced": replaced, "kept": skipped}
        if wants_project and deployments:
            wanted = {d["id"]: d for d in scope.get("deployments", []) if d["id"] in deployments}
            files = []
            for deployment_id, d in wanted.items():
                folder = pdir / d["collection"] / deployment_id  # type: ignore[operator]
                if folder.is_dir() and any(folder.iterdir()) and not replace:
                    summary["deployments"]["skipped"].append(deployment_id)
                    continue
                prefix = f"deployments/{d['collection']}/{deployment_id}/"
                for name in sorted(n for n in names if n.startswith(prefix) and not n.endswith("/")):
                    if _is_image(name) and not images:
                        continue
                    files.append((name, pdir / d["collection"] / PurePosixPath(name).relative_to(f"deployments/{d['collection']}")))  # type: ignore[operator]
                summary["deployments"]["restored"].append(deployment_id)
            # the files of the collections that the restored deployments belong to are put back where they are not
            for collection in sorted({wanted[i]["collection"] for i in summary["deployments"]["restored"]}):
                for name in sorted(n for n in names if n.startswith(f"deployments/{collection}/") and n.count("/") == 2 and not n.endswith("/")):
                    target = pdir / collection / PurePosixPath(name).name  # type: ignore[operator]
                    if replace or not target.exists():
                        files.append((name, target))
            yield {"type": "step", "message": f"Restoring {len(summary['deployments']['restored'])} deployment(s)…"}
            for index, (name, target) in enumerate(files, start=1):
                target.parent.mkdir(parents=True, exist_ok=True)
                fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.", suffix=".tmp")
                with os.fdopen(fd, "wb") as out:
                    out.write(zf.read(name))
                os.replace(tmp, target)
                summary["files"] += 1
                yield {"type": "file", "index": index, "total": len(files), "name": name}
        if settings:
            yield {"type": "step", "message": "Restoring the settings…"}
            current = config.load_settings()
            backed = json.loads(zf.read(SETTINGS))
            merged = current.model_dump(mode="json")
            for section, values in backed.items():
                if section in ("DATA", "FIELDWORK") or section not in merged or not isinstance(values, dict):
                    continue
                kept_secrets = {f: merged[section].get(f) for s, f in _SECRETS if s == section}
                merged[section] = {**merged[section], **values, **kept_secrets}
            if isinstance(backed.get("FIELDWORK"), dict):   # the people; the cameras and the SD cards are the projects'
                merged["FIELDWORK"]["trappers"] = backed["FIELDWORK"].get("trappers", merged["FIELDWORK"]["trappers"])
            try:
                config.save_settings(config.Settings.model_validate(merged))
            except Exception as exc:  # a setting the backup holds that this version does not accept
                raise BackupError(f"The settings of the backup cannot be restored: {exc}") from exc
            summary["settings"] = True
    yield {"type": "done", "summary": summary, "manifest": manifest}
