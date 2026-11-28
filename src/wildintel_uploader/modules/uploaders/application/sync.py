"""Syncing the collections folder with what TRAPPER has for a classification project — TRAPPER is read, never changed; the folder only gets
what it lacks, and what is already there is left as it is, whatever TRAPPER says —, and the images downloaded when asked. The rules are the
domain's (domain.sync); TRAPPER, the catalog and the folder are its ports."""
from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed

from wildintel_uploader.modules.uploaders.domain import sync as rules
from wildintel_uploader.modules.uploaders.domain.models import Credentials
from wildintel_uploader.modules.uploaders.domain.ports import SyncedCatalog, SyncedFolder, TrapperSite

logger = logging.getLogger(__name__)


def _say(message: str) -> dict:
    return {"type": "progress", "message": message}


class TrapperSync:
    def __init__(self, site: TrapperSite, records: Callable[[], SyncedCatalog], folder: SyncedFolder) -> None:
        self._site, self._records, self._folder = site, records, folder

    def collection_names(self, credentials: Credentials, classification_project_pk: int) -> list[str]:
        return rules.revisions(self._site.collection_names(credentials, classification_project_pk))

    def collections_with_deployments(self, credentials: Credentials, research_project_pk: int, classification_project_pk: int) -> list[dict]:
        """The collections starting with R of the classification project, each {"name", "deployments"}: the ids (upper case) of the research
        project's deployments that belong to it."""
        deployments = self._site.deployments(credentials, research_project_pk)
        return [{"name": name, "deployments": sorted(i for i, _ in rules.deployments_of(deployments, name))}
                for name in self.collection_names(credentials, classification_project_pk)]

    def sync(self, credentials: Credentials, research_project: dict, classification_project_pk: int, only: list[str] | None = None,
             only_deployments: list[str] | None = None, download_images: bool = False) -> Iterator[dict]:
        """Creates in the collections folder what TRAPPER has for the classification project and the folder lacks — one deployment at a time.
        `research_project` is {"pk", "name", "acronym"}; `only` limits it to the collections of those names, `only_deployments` to the deployments
        of those ids (any case); `download_images` brings their images too ("done" then has "downloaded"). Yields {"type": "progress"} and last
        {"type": "done"} with what was "created" and "kept" of each kind, the deployments no collection claims ("unassigned"), and those TRAPPER
        holds in a way that is not a valid deployment ("failed"), which are left out."""
        project_id = research_project.get("acronym") or str(research_project["pk"])
        folder = self._folder.project_folder(project_id)
        records = self._records()
        created: dict[str, list[str]] = {"research_project": [], "locations": [], "collections": [], "deployments": [], "images": []}
        kept: dict[str, list[str]] = {key: [] for key in created}

        if records.has_project(project_id):
            kept["research_project"].append(project_id)
            yield _say(f"Research project {project_id}: already there.")
        else:
            records.add_project(rules.new_project(research_project, project_id))
            created["research_project"].append(project_id)
            yield _say(f"Research project {project_id}: created.")

        yield _say("Reading the locations from TRAPPER…")
        locations = self._site.locations(credentials, research_project["pk"])
        known = records.location_ids(project_id)
        by_id = {}
        for location in locations:
            by_id[location["location_id"].lower()] = location
            if location["location_id"].lower() in known:
                kept["locations"].append(location["location_id"].upper())
                continue
            records.add_location(project_id, rules.new_location(location))
            created["locations"].append(location["location_id"].upper())
        yield _say(f"Locations: {len(created['locations'])} created, {len(kept['locations'])} already there.")

        yield _say("Reading the deployments and collections from TRAPPER…")
        deployments = self._site.deployments(credentials, research_project["pk"])
        names = self.collection_names(credentials, classification_project_pk)
        if only is not None:
            wanted = {n.lower() for n in only}
            names = [n for n in names if n.lower() in wanted]
        claimed: set[str] = set()
        failed: list[dict] = []
        downloaded: dict = {"images": 0, "bytes": 0, "deployments": {}, "failed": [], "not_held": {}}
        for number, name in enumerate(names, 1):
            if self._folder.has_collection(project_id, name):
                kept["collections"].append(name)
            else:
                self._folder.add_collection(project_id, name)
                created["collections"].append(name)
            mine = rules.deployments_of(deployments, name)
            claimed.update(i for i, _ in mine)   # not "unassigned" even if left out here
            if only_deployments is not None:
                wanted_ids = {d.upper() for d in only_deployments}
                mine = [(i, d) for i, d in mine if i in wanted_ids]
            yield _say(f"Collection {name} ({number}/{len(names)}): {len(mine)} deployment(s).")
            for position, (deployment_id, deployment) in enumerate(mine, 1):
                prefix = f"{deployment_id} ({position}/{len(mine)})"
                if self._folder.has_deployment(project_id, name, deployment_id):
                    kept["deployments"].append(deployment_id)
                else:
                    try:
                        self._folder.add_deployment(project_id, name, deployment_id, rules.deployment_record(deployment, deployment_id))
                    except ValueError as exc:   # one deployment TRAPPER holds badly doesn't stop the rest
                        failed.append({"deployment_id": deployment_id, "error": str(exc)})
                        yield _say(f"{prefix}: skipped, TRAPPER holds it with invalid values ({exc}).")
                        continue
                    created["deployments"].append(deployment_id)
                if self._folder.has_images(project_id, name, deployment_id):
                    kept["images"].append(deployment_id)
                else:
                    yield _say(f"{prefix}: reading its images from TRAPPER…")
                    location = by_id.get((deployment.get("location_id") or "").lower(), {})
                    images = rules.images_held(self._site.resources(credentials, deployment["pk"]), location.get("timezone"), bool(location.get("ignore_dst")))
                    self._folder.add_images(project_id, name, deployment_id, images)
                    created["images"].append(deployment_id)
                if download_images:
                    got = yield from self._download(credentials, classification_project_pk, deployment, project_id, name, deployment_id, prefix)
                    downloaded["images"] += got["downloaded"]
                    downloaded["bytes"] += got["bytes"]
                    if got["downloaded"]:
                        downloaded["deployments"][deployment_id] = got["downloaded"]
                    downloaded["failed"] += [{"deployment_id": deployment_id, **f} for f in got["failed"]]
                    if got["not_held"]:
                        downloaded["not_held"][deployment_id] = got["not_held"]
                yield _say(f"{prefix}: done.")

        unassigned = sorted(d["deployment_id"].upper() for d in deployments if d["deployment_id"] and d["deployment_id"].upper() not in claimed)
        yield {"type": "done", "research_project_id": project_id, "folder": str(folder), "created": created, "kept": kept, "unassigned": unassigned,
               "failed": failed, "collections": names, **({"downloaded": downloaded} if download_images else {})}

    def _download(self, credentials: Credentials, classification_project_pk: int, deployment: dict, project: str, collection: str, deployment_id: str,
                  prefix: str) -> Iterator[dict]:
        """Downloads into the deployment's folder the images of it the classification project holds and the folder lacks, a few at a time — what
        is there is kept. Returns {"downloaded", "bytes", "failed": [{"name", "error"}], "not_held": [the images TRAPPER lists for the deployment
        that the project doesn't hold], "already"}."""
        media = self._site.media(credentials, classification_project_pk, deployment["pk"])
        held = {m["name"] for m in media}
        not_held = sorted(set(self._folder.images_listed(project, collection, deployment_id)) - held)
        todo = [m for m in media if rules.plain_name(m["name"]) and not self._folder.has_image(project, collection, deployment_id, m["name"])]
        already = len(media) - len(todo)
        result: dict = {"downloaded": 0, "bytes": 0, "failed": [], "not_held": not_held, "already": already}
        yield _say(f"{prefix}: {len(todo)} image(s) to download" + (f", {already} already here" if already else "")
                   + (f", {len(not_held)} not in the classification project" if not_held else "") + ".")
        if not todo:
            return result
        download = self._site.downloader(credentials)
        pool = ThreadPoolExecutor(max_workers=rules.DOWNLOAD_WORKERS)
        try:
            futures = {pool.submit(download, m["url"], self._folder.image_path(project, collection, deployment_id, m["name"])): m["name"] for m in todo}
            for count, future in enumerate(as_completed(futures), 1):
                name = futures[future]
                try:
                    result["bytes"] += future.result()
                    result["downloaded"] += 1
                except Exception as exc:  # noqa: BLE001 — one image that fails doesn't stop the rest
                    logger.warning("%s: downloading %s failed: %s", deployment_id, name, exc)
                    result["failed"].append({"name": name, "error": str(exc)})
                if count % rules.PROGRESS_EVERY == 0 and count < len(todo):
                    yield _say(f"{prefix}: {count}/{len(todo)} images ({result['bytes'] / 1e6:.1f} MB).")
        finally:
            pool.shutdown(wait=True, cancel_futures=True)   # a stop doesn't leave the rest queued
        yield _say(f"{prefix}: {result['downloaded']} image(s) downloaded ({result['bytes'] / 1e6:.1f} MB)"
                   + (f", {len(result['failed'])} failed." if result["failed"] else "."))
        return result
