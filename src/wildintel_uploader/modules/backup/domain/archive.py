"""What a backup is — plain Python: the settings and the data of a research project — its locations, cameras, SD cards, visits and deployments,
with or without the images — in one archive that says what it holds (manifest.json).

The archive holds:

  manifest.json                                what it holds, of which research project, when, and by which version of the app
  settings.json                                the global settings, with no passwords or secrets and none of the folders of this computer
  project/research_project.json, locations.json, cameras.json, sd_cards.json, roles.json, status_history.json   what the research project is
  project/visits.json                          the list of visits
  deployments/<collection>/<deployment>/...    what a deployment keeps — with its images only when they were asked for
  deployments/<collection>/<name>              the files of a collection (its collection.json and its logs)

Restoring never overwrites what is there unless it is asked to; and what is archived stays archived (an archived location, camera or SD card is
archived for good)."""
from __future__ import annotations

import re
from collections.abc import Callable, Hashable
from pathlib import PurePosixPath

from wildintel_uploader.modules.backup.domain.ports import BackupError, Choice

FORMAT = "wildintel-uploader-backup"
VERSION = 1
MANIFEST = "manifest.json"
SETTINGS = "settings.json"
PROJECT = "research_project.json"
PROJECT_RECORDS = {"locations": "locations.json", "cameras": "cameras.json", "sd_cards": "sd_cards.json", "roles": "roles.json"}
VISITS = "visits.json"
HISTORY = "status_history.json"   # the history of the status of the locations, the cameras and the SD cards: it goes with the data of the project
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".gif", ".webp", ".mp4", ".avi", ".mov", ".mkv", ".m4v"}
_COLLECTION = re.compile(r"^R\d+$", re.IGNORECASE)
_DOWNLOADS = re.compile(r"^wildintel-backup_[A-Za-z0-9_.-]+_\d{8}-\d{6}\.zip$")

# how the records of a research project are known when a backup is restored: by what they are called, never by the ids of this computer
RECORD_KEYS: dict[str, Callable[[dict], Hashable]] = {
    "locations": lambda i: str(i.get("location_id", "")).lower(),
    "cameras": lambda i: str(i.get("label") or i.get("camera_id") or ""),
    "sd_cards": lambda i: str(i.get("label", "")),
    "roles": lambda i: (str(i.get("trapper", "")).lower(), i.get("role") or "contributor"),
}


def history_key(line: dict) -> Hashable:
    return (line.get("kind"), str(line.get("name", "")).lower(), line.get("at"), line.get("before"), line.get("after"))


def trapper_key(trapper: dict) -> Hashable:
    return str(trapper.get("username", "")).lower()


def is_image(name: str) -> bool:
    return PurePosixPath(name.replace("\\", "/")).suffix.lower() in IMAGE_EXTENSIONS


def is_collection(name: str) -> bool:
    return bool(_COLLECTION.match(name))


def is_download_name(name: str) -> bool:
    """A backup made to be downloaded, by its name — never a path."""
    return bool(_DOWNLOADS.match(name))


def backup_name(project: str | None, stamp: str) -> str:
    return f"wildintel-backup_{project or 'settings'}_{stamp}.zip"


def leaves_the_backup(name: str) -> bool:
    """Whether a file of the archive has a path that goes out of it. A backslash is a separator on Windows, where the files are written with it:
    it is read as one."""
    plain = name.replace("\\", "/")
    return plain.startswith("/") or ".." in PurePosixPath(plain).parts or (len(plain) > 1 and plain[1] == ":")


def folder_name(value: object, what: str) -> str:
    """A name of the manifest that is joined to a folder (a collection, a deployment): only the name of one folder inside it — no separator, no
    `..`, no drive, nothing absolute.

    Raises:
        BackupError: it is not one."""
    if not isinstance(value, str) or not value.strip() or value in (".", "..") or any(c in value for c in "/\\:\0"):
        raise BackupError(f"That backup names {what} {value!r}, which is not the name of a folder: it is not restored.")
    return value


def checked_manifest(manifest: object) -> dict:
    """The manifest of a backup of this app, of a version this one reads, whose deployments are folders of the research project.

    Raises:
        BackupError: it is not."""
    if not isinstance(manifest, dict) or manifest.get("format") != FORMAT:
        raise BackupError("That .zip is not a backup of this app.")
    if int(manifest.get("version", 0)) > VERSION:
        raise BackupError("That backup was made by a newer version of the app: update it to restore it.")
    scope = manifest.get("scope", {})
    if not isinstance(scope, dict) or not isinstance(scope.get("deployments", []), list):
        raise BackupError("That .zip is not a backup of this app: its manifest cannot be read.")
    for d in scope.get("deployments", []):
        if not isinstance(d, dict):
            raise BackupError("That .zip is not a backup of this app: its manifest cannot be read.")
        folder_name(d.get("collection"), "a collection")
        folder_name(d.get("id"), "a deployment")
    return manifest


def wanted(choice: Choice, project: str | None) -> bool:
    """Whether a backup is of a research project — what is chosen says it.

    Raises:
        BackupError: nothing was chosen, or data of a research project but not which."""
    wants_project = choice.project_files or choice.visits or bool(choice.deployments)
    if not choice.settings and not wants_project:
        raise BackupError("Nothing was chosen to put in the backup.")
    if wants_project and not project:
        raise BackupError("Choose the research project the backup is of.")
    return wants_project


def visit_key(visit: dict) -> Hashable:
    """A visit is the same one at the same site and instant."""
    return (str(visit.get("location_id", "")).lower(), visit.get("when") or f"{visit.get('date')}T{visit.get('time')}")


def merge(current: list[dict], backed: list[dict], key: Callable[[dict], Hashable], *, replace: bool) -> tuple[list[dict], int, int, int]:
    """The list kept with what the backup adds: what is there stays unless `replace` says the backup's wins — except what is archived, which is
    archived for good. Returns the list and how many were added, replaced and left as they were."""
    out = list(current)
    index = {key(item): i for i, item in enumerate(out)}
    added = replaced = skipped = 0
    for item in backed:
        k = key(item)
        if k not in index:
            index[k] = len(out)
            out.append(item)
            added += 1
        elif replace and out[index[k]].get("status") != "archived":
            # the one that is replaced is still the same one: others point to its id
            out[index[k]] = {**item, **({"id": out[index[k]]["id"]} if out[index[k]].get("id") else {})}
            replaced += 1
        else:
            skipped += 1
    return out, added, replaced, skipped


def settings_for_a_backup(settings: dict, secrets: list[tuple[str, str]], trappers: list[dict]) -> dict:
    """The global settings as they go in a backup: without passwords or secrets, and without the folders of this computer — nor the cameras and the
    SD cards, which belong to their research projects. The people are not kept in the settings but beside the research projects: they go in the
    backup of the settings, by what they are called."""
    data = {k: (dict(v) if isinstance(v, dict) else v) for k, v in settings.items()}
    for section, field in secrets:
        data[section][field] = None
    data.pop("DATA", None)
    data["FIELDWORK"] = {**data.get("FIELDWORK", {}), "cameras": [], "sd_cards": [], "roles": [], "trappers": trappers}
    return data


def settings_restored(current: dict, backed: dict, secrets: list[tuple[str, str]]) -> dict:
    """The settings with those of a backup: section by section, but the folders of this computer, the fieldwork, and the secrets kept here."""
    merged = {k: (dict(v) if isinstance(v, dict) else v) for k, v in current.items()}
    for section, values in backed.items():
        if section in ("DATA", "FIELDWORK") or section not in merged or not isinstance(values, dict):
            continue
        kept_secrets = {f: merged[section].get(f) for s, f in secrets if s == section}
        merged[section] = {**merged[section], **values, **kept_secrets}
    return merged


def people_of(backed: dict) -> list[dict]:
    """The people a backup of the settings holds — those not removed."""
    fieldwork = backed.get("FIELDWORK")
    if not isinstance(fieldwork, dict):
        return []
    return [t for t in fieldwork.get("trappers") or [] if isinstance(t, dict) and t.get("username") and not t.get("deleted_at")]
