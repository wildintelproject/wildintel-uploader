"""Repairing a deployment kept in the collections folder: the collections and the folders that are deployments, the state of one, and its
metadata written again from what the folder holds, then sealed and reported. The rules are the domain's (domain.repair); the folder, the seal,
the catalog, the reports and the settings of the preprocessing are what it is given."""
from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from wildintel_uploader.modules.catalog.domain.ports import CatalogService
from wildintel_uploader.modules.deployments.application.seal import Sealing
from wildintel_uploader.modules.deployments.domain import repair as rules
from wildintel_uploader.modules.deployments.domain.models import DeploymentMissing, DeploymentsFailed
from wildintel_uploader.modules.deployments.domain.naming import DEPLOYMENT_METADATA_FILE, IMAGES_FILE
from wildintel_uploader.modules.deployments.domain.ports import RepairFolder
from wildintel_uploader.modules.deployments.domain.seal import SEAL_FILE
from wildintel_uploader.modules.preprocessing.domain import models as pre
from wildintel_uploader.modules.reports.domain.ports import ReportsService
from wildintel_uploader.shared.errors import StorageError

logger = logging.getLogger(__name__)


def _step(name: str, status: str, message: str) -> dict:
    return {"type": "step", "step": name, "status": status, "message": message}


class Repairing:
    """`catalog` is the catalog of the collections folder the folder is of; `defaults` the settings of the preprocessing, as a dict."""

    def __init__(self, folder: RepairFolder, sealing: Callable[[], Sealing], reports: Callable[[], ReportsService], catalog: Callable[[], CatalogService],
                 defaults: Callable[[], dict], now: Callable[[], datetime] = lambda: datetime.now(timezone.utc)) -> None:
        self._folder, self._sealing, self._reports, self._catalog, self._defaults, self._now = folder, sealing, reports, catalog, defaults, now

    # ── what the contract asks: the errors as the deployments' ──

    def collections(self, project: str) -> list[dict]:
        try:
            return self.list_collections(project)
        except rules.RepairError as exc:
            raise DeploymentsFailed(str(exc)) from exc

    def inspect(self, project: str, collection: str, deployment_id: str) -> dict:
        try:
            return self.inspection(project, collection, deployment_id)
        except rules.RepairError as exc:
            raise DeploymentMissing(str(exc)) from exc

    def repair(self, project: str, collection: str, deployment_id: str) -> Iterator[dict]:
        """What fails mid-way says so with its words — what the repair itself refuses as it was, anything else as "The repair failed: …"."""
        try:
            events = self.repair_stream(project, collection, deployment_id)
        except rules.RepairError as exc:
            raise DeploymentsFailed(str(exc)) from exc

        def told() -> Iterator[dict]:
            try:
                yield from events
            except DeploymentsFailed as exc:
                raise DeploymentsFailed(str(exc)) from exc
            except StorageError as exc:
                raise DeploymentsFailed(str(exc)) from exc
            except Exception as exc:  # noqa: BLE001
                raise DeploymentsFailed(f"The repair failed: {exc}") from exc
        return told()

    # ── what is there ──

    def _deployment(self, project: str, collection: str, deployment_id: str) -> Path:
        rules.check_names(collection, deployment_id)
        dest = self._folder.collection(project, collection) / deployment_id
        if dest not in self._folder.folders(dest.parent):
            raise rules.RepairError(f"{deployment_id} isn't in the collection {collection}.")
        return dest

    def list_collections(self, project: str) -> list[dict]:
        """The collections kept for a research project and the folders in each that are deployments — whatever state they are in, even one with
        no metadata at all. Cheap: nothing is read but the folder's names."""
        out = []
        for name, path in self._folder.collections(project):
            if not rules.is_collection(name):
                continue
            deployments = [{"deployment_id": f.name, "images": len(self._folder.images(f)),
                            "files": {n: self._folder.file_state(f, n) != "missing" for n in rules.METADATA_FILES}, "synced": self._folder.synced(f)}
                           for f in self._folder.folders(path) if rules.is_deployment(f.name)]
            out.append({"name": name, "path": str(path), "deployments": deployments})
        return out

    def _log(self, collection_dir: Path, deployment_id: str) -> tuple[dict | None, str]:
        row, problem = self._folder.log_row(collection_dir, deployment_id)
        return row, problem or ("row" if row else ("no row" if self._folder.has_log(collection_dir) else "no log"))

    def inspection(self, project: str, collection: str, deployment_id: str) -> dict:
        dest = self._deployment(project, collection, deployment_id)
        files = {name: self._folder.file_state(dest, name) for name in rules.METADATA_FILES}
        _, log = self._log(dest.parent, deployment_id)
        synced = self._folder.synced(dest)
        return rules.inspection(deployment_id, files, len(self._folder.images(dest)), log, synced, None if synced else self._sealing().verify(dest))

    # ── repairing ──

    def repair_stream(self, project: str, collection: str, deployment_id: str) -> Iterator[dict]:
        """Repairs one deployment. Events: {"type": "step", "step", "status", "message"} — "inspect", "dates", "deployment", "preprocessing",
        "images", "seal" — and, last, {"type": "done", "deployment_id", "images", "written", "problems", "status", "report_id"}. RepairError when the
        deployment isn't there or was synced from TRAPPER; mid-way, when what is needed to rebuild it isn't known."""
        dest = self._deployment(project, collection, deployment_id)
        if self._folder.synced(dest):
            raise rules.RepairError(f"{deployment_id} was synced from TRAPPER, so it can't be modified here.")
        return self._events(project, deployment_id, dest)

    def _events(self, project: str, deployment_id: str, dest: Path) -> Iterator[dict]:
        folder = self._folder
        old_deployment = folder.read_json(dest, DEPLOYMENT_METADATA_FILE)
        old_deployment = old_deployment if isinstance(old_deployment, dict) else None
        old_log = folder.read_json(dest, pre.PREPROCESSING_LOG_FILE)
        old_log = old_log if isinstance(old_log, dict) and isinstance(old_log.get("images"), list) else None
        old_records = {r["name"]: r for r in (old_log or {}).get("images", []) if isinstance(r, dict) and "name" in r}
        written: list[str] = []
        file_results: list[tuple[str, bool, str]] = []

        yield _step("inspect", "running", "Looking at the folder…")
        images = folder.images(dest)
        names = [str(p.relative_to(dest)) for p in images]
        yield _step("inspect", "done", f"{len(images)} image(s), {sum(folder.file_state(dest, n) != 'missing' for n in rules.METADATA_FILES)} of "
                                       f"{len(rules.METADATA_FILES)} metadata files.")

        catalog = self._catalog()
        wanted = (old_deployment or {}).get("location_id") or (deployment_id.split("-", 1)[1] if "-" in deployment_id else None)
        found = next((loc for loc in catalog.locations(project) if wanted and str(loc.location_id).lower() == wanted.lower()), None)
        location = {"location_id": found.location_id, "name": found.name, "latitude": found.latitude, "longitude": found.longitude,
                    "coordinate_uncertainty": found.coordinate_uncertainty} if found else {}
        location_id = location.get("location_id") or wanted
        location_time = catalog.location_time(project, location_id)
        zone_name = location_time.get("timezone") or ((old_log or {}).get("options") or {}).get("timezone")
        options = rules.options_of(self._defaults(), old_log, location_time, zone_name)
        zone = rules.zone(zone_name or options.timezone)
        ignore_dst = location_time["ignore_dst"] if location_time.get("ignore_dst") is not None else options.ignore_dst

        # ── when it was: the timestamp log prevails over the images ──
        yield _step("dates", "running", "Reading the capture dates and the timestamp log…")
        dates = folder.taken(images)   # one run of ExifTool for all of them (#227)
        times = {}
        for path in images:
            naive, source = dates.get(path), "exif"
            if naive is None:
                naive, source = folder.modified(path), "file"
            times[path] = (naive, pre.localize(naive, rules.zone(options.timezone), ignore_dst=options.ignore_dst), source)
        exif_times = [t[0] for t in times.values() if t[2] == "exif"] or [t[0] for t in times.values()]
        computed = (min(exif_times), max(exif_times)) if exif_times else None
        row, problem = folder.log_row(dest.parent, deployment_id)
        if problem and folder.has_log(dest.parent):
            raise rules.RepairError(problem)
        start, end, note = rules.period(deployment_id, row, old_deployment, computed)
        yield _step("dates", "done", f"{start:%Y-%m-%d %H:%M:%S} → {end:%Y-%m-%d %H:%M:%S} ({note}).")

        # ── deployment.json ──
        yield _step("deployment", "running", "Writing deployment.json…")
        cameras = folder.cameras(images)
        record = rules.deployment_record(deployment_id, location_id, location, {c.model for c in cameras.values() if c.model},
                                         {c.camera_id for c in cameras.values() if c.camera_id}, old_deployment,
                                         pre.localize(start, zone, ignore_dst=ignore_dst).isoformat(), pre.localize(end, zone, ignore_dst=ignore_dst).isoformat())
        try:
            deployment = folder.as_deployment(record)
        except ValueError as exc:
            file_results.append((DEPLOYMENT_METADATA_FILE, False, f"could not be rebuilt — {exc}"))
            raise rules.RepairError(f"deployment.json can't be rebuilt: {exc}. Add what is missing (the location's coordinates, for one) and repair it again.") from exc
        body = folder.record_of(deployment)
        if old_deployment != body:
            folder.write_deployment(dest, body)
            written.append(DEPLOYMENT_METADATA_FILE)
            what = rules.what_changed(old_deployment, body)
            file_results.append((DEPLOYMENT_METADATA_FILE, True, what))
            yield _step("deployment", "done", f"deployment.json {what}.")
        else:
            file_results.append((DEPLOYMENT_METADATA_FILE, True, "was fine"))
            yield _step("deployment", "done", "deployment.json was fine.")

        # ── preprocessing.json and images.json, from the images ──
        records: list[dict] = []
        sealed = None
        xmp: dict[Path, dict] = {}
        if not images:
            for name in ("preprocessing", "images", "seal"):
                yield _step(name, "skipped", "There are no images.")
        else:
            yield _step("preprocessing", "running", "Rebuilding preprocessing.json from the images…")
            xmp = folder.xmp(images)
            hashes = dict(zip(images, folder.sha1s(images)))
            for path, name in zip(images, names):
                naive, aware, source = times[path]
                date = aware.astimezone(timezone.utc) if options.convert_to_utc else aware
                before = old_records.get(name, {})
                width, height = folder.dimensions(path)
                records.append({
                    "original": before.get("original", name), "name": name, "date": date.isoformat(), "date_source": source, "resized": before.get("resized"),
                    "source_hash": before.get("source_hash") or xmp.get(path, {}).get("source_hash"), "hash": before.get("hash") or hashes[path],
                    "final_hash": hashes[path], "camera": cameras[path].model if path in cameras else None,
                    "camera_id": cameras[path].camera_id if path in cameras else None, "width": width, "height": height,
                    "_local": naive, "_date": date, "_size": folder.size(path),
                })
            public = [{k: v for k, v in r.items() if not k.startswith("_")} for r in records]
            options_body = {**asdict(options), "timezone": zone_name or options.timezone, "ignore_dst": ignore_dst}
            folder.write_preprocessing(dest, {"options": options_body, "processed": len(public), "skipped": (old_log or {}).get("skipped", 0), "images": public,
                                              "recovered": {"at": self._now().isoformat(timespec="seconds"), "from": "the images in the folder"}})
            written.append(pre.PREPROCESSING_LOG_FILE)
            file_results.append((pre.PREPROCESSING_LOG_FILE, True, "rebuilt" if old_log is None else "rebuilt from the images and what was left of it"))
            missing_source = sum(1 for r in records if not r["source_hash"])
            yield _step("preprocessing", "done", f"preprocessing.json written for {len(records)} image(s)"
                                                 + (f"; {missing_source} without the hash of their original" if missing_source else "") + ".")

            yield _step("images", "running", "Rebuilding images.json…")
            folder.write_images(dest, deployment_id, [(r["name"], r["_local"].isoformat(), {
                "original": r["original"], "taken_at": r["date"], "timestamp": r["_date"].timestamp(), "date_source": r["date_source"], "camera": r["camera"],
                "camera_id": r.get("camera_id"), "width": r["width"], "height": r["height"], "size_bytes": r["_size"], "resized": r["resized"],
                "sha1": r["final_hash"], "source_sha1": r["source_hash"]}) for r in records])
            written.append(IMAGES_FILE)
            file_results.append((IMAGES_FILE, True, "rebuilt from the images"))
            yield _step("images", "done", f"images.json written: {len(records)} image(s).")

            # ── validate, postvalidate, seal ──
            yield _step("seal", "running", "Validating and postvalidating the images, and sealing…")
            sealed = self._sealing().seal(dest, dest, deployment, source_hashes={r["name"]: r["source_hash"] for r in records if r["source_hash"]},
                                          preprocessing=options_body, recovered=True)
            written.append(SEAL_FILE)
            file_results.append((SEAL_FILE, True, "written again"))
            failed = sum(1 for e in sealed["images"] for v in (*e["validations"].values(), *e["postvalidations"].values()) if v != "ok")
            yield _step("seal", "done", "Sealed. " + (f"{failed} problem(s) found in the images." if failed else "The images passed every check."))

        identified = {str(p.relative_to(dest)): bool(x.get("identifier")) for p, x in xmp.items()}
        preprocessing = rules.preprocessing_problems(deployment_id, records, options, old_records, identified) if records else {}
        report_id = None
        try:
            report_id = self._reports().save_repair(deployment_id, dest, file_results, sealed, preprocessing)
        except Exception as exc:  # noqa: BLE001 — the repair is done: not having its report is no reason to fail it
            logger.warning("Could not write the report of the repair of %s: %s", deployment_id, exc)
        status = self._sealing().verify(dest)["status"] if sealed else "unsealed"
        problems = self._reports().read(report_id)["totals"]["failed"] if report_id else 0
        logger.info("Deployment %s repaired: wrote %s", deployment_id, ", ".join(written))
        yield {"type": "done", "deployment_id": deployment_id, "images": len(images), "written": written, "problems": problems,
               "status": rules.STATUS.get(status, status), "report_id": report_id}

