"""The use cases of the backups: what a research project has that can go in one, a backup made — in a folder, or to be downloaded —, what one
holds and what of it is already here, and what is chosen of it restored. What can't be done at all is said before anything is written: the first
step is taken before answering."""
from __future__ import annotations

import json
import logging
from collections.abc import Callable, Iterator
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from wildintel_uploader.modules.backup.domain import archive as rules
from wildintel_uploader.modules.backup.domain.ports import (
    AppSettings, Archives, BackupError, BackupGone, BackupService, Choice, Entry, ProjectFolders, ProjectRecords,
)

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _first_then(events: Iterator[dict], what: str, empty: dict | None = None) -> Iterator[dict]:
    """The events, the first taken now — what can't be done at all is said before answering; what fails later says what failed."""
    def told() -> Iterator[dict]:
        try:
            yield from events
        except BackupError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning("%s failed: %s", what, exc, exc_info=True)
            raise BackupError(f"{what} failed: {exc}") from exc
    stream = told()
    try:
        first = next(stream)
    except StopIteration:
        first = empty
    def chained() -> Iterator[dict]:
        if first is not None:
            yield first
        yield from stream
    return chained()


class BackupUseCases(BackupService):
    def __init__(self, records: ProjectRecords, folders: ProjectFolders, archives: Archives, settings: AppSettings, version: Callable[[], str],
                 now: Callable[[], datetime] = _now) -> None:
        self._records, self._folders, self._archives, self._settings, self._version, self._now = records, folders, archives, settings, version, now

    # ── what a research project has ──

    def describe(self, project: str) -> dict:
        """What a research project has that can be put in a backup: how many locations, cameras, SD cards and visits, and each deployment of each
        collection with its files and how many bytes they are — those that are images apart."""
        self._records.require_project(project)
        collections = []
        for collection in (c for c in self._folders.collections(project) if rules.is_collection(c)):
            deployments = []
            for deployment in self._folders.deployments(project, collection):
                files = self._folders.deployment_files(project, collection, deployment) or []
                images = [f for f in files if rules.is_image(f.name)]
                deployments.append({"id": deployment, "files": len(files), "bytes": sum(f.size for f in files),
                                    "images": len(images), "image_bytes": sum(f.size for f in images)})
            collections.append({"name": collection, "deployments": deployments})
        return {
            "research_project_id": project,
            "locations": len(self._records.locations(project)),
            "cameras": len(self._records.equipment(project, "cameras")),
            "sd_cards": len(self._records.equipment(project, "sd_cards")),
            "visits": self._records.kept_visits(project),
            "collections": collections,
        }

    # ── making one ──

    def settings_snapshot(self) -> dict:
        """The global settings as they go in a backup."""
        return rules.settings_for_a_backup(self._settings.as_data(), self._settings.secrets(), self._records.trappers())

    def create(self, dest_dir: Path | None, project: str | None, choice: Choice) -> Iterator[dict]:
        staged = dest_dir is None
        events = _first_then(self._made(self._archives.staging_dir() if staged else dest_dir, project, choice), "The backup")

        def told() -> Iterator[dict]:
            for event in events:
                # made to be downloaded: the last event says which file the browser asks for
                yield {**event, "download": Path(event["path"]).name} if staged and event.get("type") == "done" else event
        return told()

    def _made(self, dest_dir: Path, project: str | None, choice: Choice) -> Iterator[dict]:
        self._archives.check_destination(dest_dir)
        wants_project = rules.wanted(choice, project)
        yield {"type": "step", "message": "Looking at what is going in…"}
        entries: list[Entry] = []
        scope: dict = {"settings": choice.settings, "research_project": project if wants_project else None, "project_files": choice.project_files,
                       "visits": choice.visits, "images": choice.images, "deployments": []}
        if choice.settings:
            entries.append(Entry(rules.SETTINGS, data=self.settings_snapshot()))
        counts: dict = {}
        if wants_project:
            assert project is not None
            info = self.describe(project)
            if choice.project_files:
                if (record := self._records.project_record(project)) is not None:
                    entries.append(Entry(f"project/{rules.PROJECT}", data=record))
                for kind, name in rules.PROJECT_RECORDS.items():
                    # what is kept points to other things by their ids, which are the app's own: the backup says them by what they are called
                    records = (self._records.roles(project, include_deleted=True) if kind == "roles"
                               else self._records.location_records(project) if kind == "locations"
                               else self._records.equipment_records(project, kind))
                    if records:
                        entries.append(Entry(f"project/{name}", data=records))
                if history := self._records.status_history(project):
                    entries.append(Entry(f"project/{rules.HISTORY}", data=history))
                counts.update({"locations": info["locations"], "cameras": info["cameras"], "sd_cards": info["sd_cards"]})
            if choice.visits and (kept := self._records.visits(project)):
                entries.append(Entry(f"project/{rules.VISITS}", data=kept))
                counts["visits"] = info["visits"]
            done_collections: set[str] = set()
            for deployment_id in choice.deployments:
                collection = deployment_id.split("-", 1)[0].upper()
                files = self._folders.deployment_files(project, collection, deployment_id)
                if files is None:
                    raise BackupError(f"The deployment {deployment_id} is not in {project}.")
                kept_files = [f for f in files if choice.images or not rules.is_image(f.name)]
                entries += [Entry(f"deployments/{collection}/{deployment_id}/{f.name}", path=f.path) for f in kept_files]
                scope["deployments"].append({"id": deployment_id, "collection": collection, "files": len(kept_files), "images": choice.images})
                if collection not in done_collections:
                    done_collections.add(collection)
                    entries += [Entry(f"deployments/{collection}/{f.name}", path=f.path) for f in self._folders.collection_files(project, collection)]
        now = self._now()
        manifest = {
            "format": rules.FORMAT, "version": rules.VERSION, "app_version": self._version(), "created_at": now.isoformat(timespec="seconds"),
            "scope": scope, "counts": counts, "secrets_included": False,
        }
        name = rules.backup_name(project if wants_project else None, now.astimezone().strftime("%Y%m%d-%H%M%S"))
        target, size = yield from self._archives.make(dest_dir, name, manifest, entries)
        yield {"type": "done", "path": str(target), "bytes": size, "files": len(entries) + 1, "manifest": manifest}

    def download(self, name: str) -> Path:
        if not rules.is_download_name(name):
            raise BackupGone("There is no such backup.")
        path = self._archives.staging_dir() / name
        if not self._archives.is_there(path):
            raise BackupGone("That backup is not there any more: make it again.")
        return path

    # ── reading one ──

    @staticmethod
    def _manifest(archive) -> dict:
        try:
            manifest = json.loads(archive.read(rules.MANIFEST))
        except (KeyError, ValueError) as exc:
            raise BackupError("That .zip is not a backup of this app: it has no manifest.") from exc
        return rules.checked_manifest(manifest)

    def read(self, path: Path) -> dict:
        """What a backup holds — its manifest — and what of it is already here: the research project, each deployment, and how many of its visits
        (the same site and instant) are already kept."""
        with self._archives.open(path) as archive:
            manifest = self._manifest(archive)
            names = archive.names()
            scope = manifest.get("scope", {})
            project = scope.get("research_project")
            here: dict = {"project": False, "deployments": {}, "visits": {"in_backup": 0, "already": 0}}
            if project:
                self._folders.check_project(project)
                here["project"] = self._records.has_project(project)
                for d in scope.get("deployments", []):
                    here["deployments"][d["id"]] = self._folders.holds(project, f"{d['collection']}/{d['id']}")
                if f"project/{rules.VISITS}" in names:
                    backed = json.loads(archive.read(f"project/{rules.VISITS}"))
                    mine = {rules.visit_key(v) for v in self._records.visits(project)} if here["project"] else set()
                    here["visits"] = {"in_backup": len(backed), "already": sum(rules.visit_key(v) in mine for v in backed)}
            has_images = {d["id"]: any(n.startswith(f"deployments/{d['collection']}/{d['id']}/") and rules.is_image(n) for n in names)
                          for d in scope.get("deployments", [])}
        return {"manifest": manifest, "here": here, "has_images": has_images}

    # ── restoring ──

    def restore(self, path: Path, choice: Choice, replace: bool) -> Iterator[dict]:
        return _first_then(self._restored(path, choice, replace), "The restoration", empty={"type": "done", "summary": {}})

    def _restored(self, path: Path, choice: Choice, replace: bool) -> Iterator[dict]:
        records, folders = self._records, self._folders
        with self._archives.open(path) as archive:
            manifest = self._manifest(archive)
            scope = manifest.get("scope", {})
            names = archive.names()
            project = scope.get("research_project")
            summary: dict = {"settings": False, "project_files": {}, "visits": {}, "deployments": {"restored": [], "skipped": []}, "files": 0}
            if choice.settings and rules.SETTINGS not in names:
                raise BackupError("That backup holds no settings.")
            wants_project = choice.project_files or choice.visits or bool(choice.deployments)
            if wants_project and not project:
                raise BackupError("That backup holds no research project.")
            if wants_project:
                folders.check_project(project)
                for d in choice.deployments:
                    if not any(x["id"] == d for x in scope.get("deployments", [])):
                        raise BackupError(f"The deployment {d} is not in that backup.")
                if not records.has_project(project) and not (choice.project_files and f"project/{rules.PROJECT}" in names):
                    raise BackupError(f"The research project {project} is not here: restore its data too.")

            def backed(name: str) -> list[dict]:
                return [i for i in json.loads(archive.read(name)) if isinstance(i, dict)]

            if wants_project and choice.project_files:
                yield {"type": "step", "message": f"Restoring the data of {project}…"}
                if f"project/{rules.PROJECT}" in names:
                    if replace or records.project_record(project) is None:
                        # as the backup has it — its id and dates too —, wherever the catalog is kept
                        records.put_project_record(json.loads(archive.read(f"project/{rules.PROJECT}")))
                        folders.make_project(project)
                        summary["project_files"]["research_project"] = "written"
                    else:
                        summary["project_files"]["research_project"] = "kept"
                for kind, file_name in rules.PROJECT_RECORDS.items():
                    if f"project/{file_name}" not in names:
                        continue
                    items, key = backed(f"project/{file_name}"), rules.RECORD_KEYS[kind]
                    if kind == "roles":   # told by the name of the trapper: it is kept by its id, whoever the trapper is here
                        merged, added, replaced, skipped = rules.merge(records.roles(project), [r for r in items if not r.get("deleted_at")], key, replace=replace)
                        records.keep_roles(project, merged)
                    elif kind == "locations":
                        merged, added, replaced, skipped = rules.merge(records.location_records(project), items, key, replace=replace)
                        records.put_location_records(project, merged)
                    else:   # the cameras and the SD cards
                        merged, added, replaced, skipped = rules.merge(records.equipment_records(project, kind), items, key, replace=replace)
                        records.put_equipment_records(project, kind, merged)
                    summary["project_files"][kind] = {"added": added, "replaced": replaced, "kept": skipped}
                if f"project/{rules.HISTORY}" in names:   # a line of the history is never changed: the ones the backup has that are not here are added
                    merged, added, _, skipped = rules.merge(records.status_history(project), backed(f"project/{rules.HISTORY}"), rules.history_key, replace=False)
                    records.keep_status_history(project, sorted(merged, key=lambda line: str(line.get("at", ""))))
                    summary["project_files"]["status_history"] = {"added": added, "replaced": 0, "kept": skipped}
            if wants_project and choice.visits:
                yield {"type": "step", "message": f"Restoring the visits of {project}…"}
                if f"project/{rules.VISITS}" not in names:
                    raise BackupError("That backup holds no visits.")
                merged, added, replaced, skipped = rules.merge(records.visits(project), backed(f"project/{rules.VISITS}"), rules.visit_key, replace=replace)
                records.replace_visits(project, merged)
                summary["visits"] = {"added": added, "replaced": replaced, "kept": skipped}
            if wants_project and choice.deployments:
                wanted = {d["id"]: d for d in scope.get("deployments", []) if d["id"] in choice.deployments}
                files: list[tuple[str, str]] = []   # (name in the archive, path in the research project)
                for deployment_id, d in wanted.items():
                    if folders.holds(project, f"{d['collection']}/{deployment_id}") and not replace:
                        summary["deployments"]["skipped"].append(deployment_id)
                        continue
                    collection_dir = f"deployments/{d['collection']}"
                    prefix = f"{collection_dir}/{deployment_id}/"
                    for name in sorted(n for n in names if n.startswith(prefix) and not n.endswith("/")):
                        if rules.is_image(name) and not choice.images:
                            continue
                        files.append((name, f"{d['collection']}/{PurePosixPath(name).relative_to(collection_dir)}"))
                    summary["deployments"]["restored"].append(deployment_id)
                # the files of the collections that the restored deployments belong to are put back where they are not
                for collection in sorted({wanted[i]["collection"] for i in summary["deployments"]["restored"]}):
                    for name in sorted(n for n in names if n.startswith(f"deployments/{collection}/") and n.count("/") == 2 and not n.endswith("/")):
                        relative = f"{collection}/{PurePosixPath(name).name}"
                        if replace or not folders.holds(project, relative):
                            files.append((name, relative))
                folders.check_inside(project, [relative for _, relative in files])   # every file goes inside the research project, or none is written
                yield {"type": "step", "message": f"Restoring {len(summary['deployments']['restored'])} deployment(s)…"}
                for index, (name, relative) in enumerate(files, start=1):
                    folders.write(project, relative, archive.read(name))
                    summary["files"] += 1
                    yield {"type": "file", "index": index, "total": len(files), "name": name}
            if choice.settings:
                yield {"type": "step", "message": "Restoring the settings…"}
                from_backup = json.loads(archive.read(rules.SETTINGS))
                merged_settings = rules.settings_restored(self._settings.as_data(), from_backup, self._settings.secrets())
                fieldwork = from_backup.get("FIELDWORK")
                if isinstance(fieldwork, dict) and fieldwork.get("trappers"):   # the people, kept beside the projects
                    kept, added, replaced, skipped = rules.merge(records.trappers(), rules.people_of(from_backup), rules.trapper_key, replace=replace)
                    records.keep_trappers(kept)
                    summary["trappers"] = {"added": added, "replaced": replaced, "kept": skipped}
                self._settings.save(merged_settings)
                summary["settings"] = True
        yield {"type": "done", "summary": summary, "manifest": manifest}
