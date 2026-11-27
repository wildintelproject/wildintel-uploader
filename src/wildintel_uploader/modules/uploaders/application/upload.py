"""Uploading a deployment kept in the collections folder to TRAPPER — or only saying what that would do ("dry_run"), or only writing the files
("generate") —, and checking beforehand what the account can do there, changing nothing. The rules are the domain's (domain.trapper); TRAPPER, the
deployment kept and the packages are its ports."""
from __future__ import annotations

import queue
import threading
import time
from collections.abc import Callable, Iterator
from datetime import datetime, timezone
from pathlib import Path

from wildintel_uploader.modules.uploaders.domain import trapper as rules
from wildintel_uploader.modules.uploaders.domain.models import Credentials, UploaderError
from wildintel_uploader.modules.uploaders.domain.ports import KeptDeployment, PackagePart, Packages, TrapperSite


def with_progress(work: Callable[[Callable[[dict], None]], None]) -> Iterator[dict]:
    """Runs `work(report)` — blocking, and calling report(event) as it goes — in a thread, yielding what it reports as it does, and raising
    whatever it raises."""
    events: queue.Queue = queue.Queue()
    failure: list[BaseException] = []

    def run() -> None:
        try:
            work(events.put)
        except BaseException as exc:  # noqa: BLE001 — handed to the caller below
            failure.append(exc)
        finally:
            events.put(None)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    while (event := events.get()) is not None:
        yield event
    thread.join()
    if failure:
        raise failure[0]


def _step(name: str, status: str, message: str, url: str | None = None) -> dict:
    event = {"type": "step", "step": name, "status": status, "message": message}
    if url:
        event["url"] = url  # where to look at it in TRAPPER
    return event


class TrapperUploads:
    def __init__(self, site: TrapperSite, kept: KeptDeployment, packages: Packages, *, sleep: Callable[[float], None] = time.sleep,
                 monotonic: Callable[[], float] = time.monotonic, now: Callable[[], datetime] = lambda: datetime.now(timezone.utc)) -> None:
        self._site, self._kept, self._packages = site, kept, packages
        self._sleep, self._monotonic, self._now = sleep, monotonic, now

    # ── what TRAPPER has ──

    def research_project_pk(self, credentials: Credentials, record: dict) -> int:
        return rules.research_project_pk(self._site.research_projects(credentials), record)

    def classification_project(self, credentials: Credentials, research_project_pk: int, chosen: int | None = None) -> dict:
        return rules.classification_project(self._site.classification_projects(credentials, research_project_pk), chosen)

    def location(self, credentials: Credentials, research_project_pk: int, deployment) -> dict | None:
        """The deployment's location as TRAPPER has it, or None. UploaderError when the deployment has none."""
        return rules.location_named(self._site.locations(credentials, research_project_pk), rules.needs_location(deployment.location_id))

    def deployment(self, credentials: Credentials, research_project_pk: int, deployment) -> dict | None:
        return rules.deployment_named(self._site.deployments(credentials, research_project_pk), deployment.deployment_id)

    def ensure_location(self, credentials: Credentials, research_project_pk: int, deployment, timezone_name: str, ignore_dst: bool) -> bool:
        """Creates the deployment's location in TRAPPER when its research project doesn't have it yet; True when it was created."""
        if self.location(credentials, research_project_pk, deployment) is not None:
            return False
        self._site.create_location(credentials, research_project_pk, deployment, timezone_name, ignore_dst)
        return True

    def ensure_deployment(self, credentials: Credentials, research_project_pk: int, deployment, timezone_name: str, ignore_dst: bool) -> bool:
        """Creates the deployment in TRAPPER when its research project doesn't have it yet — in its location named as TRAPPER has it: TRAPPER
        keeps the ids of its locations in lower case and looks them up as they are —; True when it was created."""
        if self.deployment(credentials, research_project_pk, deployment) is not None:
            return False
        location = self.location(credentials, research_project_pk, deployment)
        self._site.create_deployment(credentials, research_project_pk, deployment, timezone_name, ignore_dst,
                                     location["location_id"] if location else deployment.location_id)
        return True

    # ── checking, changing nothing ──

    def check_access(self, credentials: Credentials, research_project: dict, location_ids: list[str] | None = None, *,
                     classification_project_pk: int | None = None, describe: Callable[[Exception], str] = str) -> list[dict]:
        """Whether this account can do what an upload needs — [{"check", "ok", "message"}] —: the research project, the classification project the
        collection will go to, the locations (and whether those of the deployments are there or would be created), and the uploader's login. Each
        check is independent: one failing doesn't stop the others."""
        checks: list[dict] = []

        def check(name: str, ok: bool, message: str) -> None:
            checks.append({"check": name, "ok": ok, "message": message})

        project_pk: int | None = None
        try:
            project_pk = self.research_project_pk(credentials, research_project)
            check("research_project", True, f"Research project {research_project.get('acronym')} is #{project_pk} in TRAPPER.")
        except Exception as exc:  # noqa: BLE001 — told, and the other checks go on
            check("research_project", False, describe(exc))
        if project_pk is None:
            check("classification_project", False, "Not checked: the research project couldn't be found.")
            check("location", False, "Not checked: the research project couldn't be found.")
        else:
            try:
                chosen = self.classification_project(credentials, project_pk, classification_project_pk)
                check("classification_project", True, f"The revision will go to the classification project {chosen['name']} (#{chosen['pk']}).")
            except Exception as exc:  # noqa: BLE001
                check("classification_project", False, describe(exc))
            try:
                known = {loc["location_id"].lower() for loc in self._site.locations(credentials, project_pk)}
                check("location", True, rules.locations_message(known, location_ids))
            except Exception as exc:  # noqa: BLE001
                check("location", False, describe(exc))
        try:
            self._site.log_in_to_uploader(credentials)
            check("uploader", True, f"Logged in to the uploader at {credentials[0].rstrip('/')}/uploader.")
        except Exception as exc:  # noqa: BLE001
            check("uploader", False, describe(exc))
        return checks

    def check_selection(self, credentials: Credentials, research_project: dict, collection: str | None = None, *,
                        describe: Callable[[Exception], str] = str) -> list[dict]:
        """What the account sees of the research project and of the collection about to be uploaded — whether TRAPPER already has it ("found": the
        upload adds to it) or not (the upload creates it) —, changing nothing. With no collection, only the research project is checked."""
        try:
            project_pk = self.research_project_pk(credentials, research_project)
        except Exception as exc:  # noqa: BLE001
            return [{"check": "research_project", "ok": False, "message": describe(exc)},
                    *([{"check": "collection", "ok": False, "message": "Not checked: the research project couldn't be found."}] if collection else [])]
        checks = [{"check": "research_project", "ok": True,
                   "message": f"You have access to the research project {research_project.get('acronym')} (#{project_pk}) in TRAPPER."}]
        if not collection:
            return checks   # only the research project was asked: the revision is looked for once it is chosen
        named = rules.collection_name(research_project, collection)
        try:
            found = self._site.collection(credentials, project_pk, named)
            message = (f"You have access to the revision {named} (#{found['pk']}): it is already in TRAPPER, so the upload adds to it." if found else
                       f"You can read the revisions of the research project; {named} isn't in TRAPPER yet, so the upload creates it.")
            checks.append({"check": "collection", "ok": True, "found": bool(found), "message": message})
        except Exception as exc:  # noqa: BLE001
            checks.append({"check": "collection", "ok": False, "message": describe(exc)})
        return checks

    # ── the packages ──

    def _entries(self, deployment_dir: Path, log: dict) -> list[dict]:
        names = [e["name"] for e in log.get("images", [])]
        return rules.images_to_send(str(deployment_dir), log, self._kept.missing(deployment_dir, names))

    def _parts(self, deployment_dir: Path, entries: list[dict], max_zip_bytes: int | None) -> list[list[dict]]:
        sizes = self._kept.sizes(deployment_dir, [e["name"] for e in entries])
        return rules.split_by_size(list(zip(sizes, entries)), max_zip_bytes)

    def plan(self, deployment_dir: Path, log: dict, max_zip_bytes: int | None = rules.DEFAULT_MAX_ZIP_BYTES) -> dict:
        """How the images would be packed, without packing anything: {"images", "parts", "bytes"}."""
        entries = self._entries(deployment_dir, log)
        return {"images": len(entries), "parts": len(self._parts(deployment_dir, entries, max_zip_bytes)),
                "bytes": sum(self._kept.sizes(deployment_dir, [e["name"] for e in entries]))}

    def build(self, deployment_dir: Path, collection: str, deployment_id: str, log: dict, *, project_id: int, timezone_name: str, ignore_dst: bool,
              output_dir: Path, max_zip_bytes: int | None = rules.DEFAULT_MAX_ZIP_BYTES, stamp: str | None = None,
              trapper_deployment_id: str | None = None, progress: Callable[[int, int], None] | None = None):
        """Packs a deployment's images — as its preprocessing recorded them — into one or more zip + yaml pairs in output_dir, naming the
        deployment as TRAPPER has it (else as it is kept here), in lower case: TRAPPER keeps its ids so and looks them up as they are."""
        entries = self._entries(deployment_dir, log)
        named = (trapper_deployment_id or deployment_id).lower()
        stamp = stamp or self._now().astimezone().strftime("%Y%m%d%H%M%S")
        parts = [PackagePart(rules.package_base(project_id, stamp, collection, deployment_id, index), collection, project_id, timezone_name, ignore_dst,
                             named, deployment_dir, part) for index, part in enumerate(self._parts(deployment_dir, entries, max_zip_bytes), start=1)]
        return self._packages.build(output_dir, parts, progress or (lambda done, total: None))

    # ── uploading ──

    def upload(self, credentials: Credentials | None, research_project: dict, collection_dir: Path, deployment_id: str, packages_dir: Path, *,
               mode: str = "upload", max_zip_bytes: int | None = rules.DEFAULT_MAX_ZIP_BYTES, remove_zip: bool = True, delete_after_upload: bool = True,
               wait_seconds: float | None = None, poll_seconds: float | None = None, classification_project_pk: int | None = None) -> Iterator[dict]:
        """Uploads one deployment of a collection to TRAPPER — or, as `mode` says, only shows what that would do ("dry_run"), or only writes the
        files ("generate"). Events: {"type": "step", "step", "status": "running" | "done" | "skipped", "message"} for the steps "connect",
        "classification", "uploader", "location", "deployment", "package", "csv", "upload", "process" and "wait"; {"type": "upload_progress"} while a
        file goes up; {"type": "pack_progress", "index", "total"} while the images are packed; {"type": "package_ready", "images", "parts", "bytes"};
        and {"type": "done", "mode", "collection", "deployment_id", …}.

        Once it is uploaded, `delete_after_upload` takes the package files away — the zips, the yamls and the deployment's row of the collection's
        deployments csv; without it they are kept (the csv is written then), and "done" says where. A dry run changes nothing. Generating needs no
        connection to TRAPPER when the research project's pk there is already known: credentials may then be None."""
        if mode not in rules.MODES:
            raise UploaderError(f"Unknown mode '{mode}' — use one of {', '.join(rules.MODES)}.")
        wait_seconds = rules.WAIT_FOR_COLLECTION_SECONDS if wait_seconds is None else wait_seconds
        poll_seconds = rules.POLL_SECONDS if poll_seconds is None else poll_seconds
        deployment_dir = collection_dir / deployment_id
        collection = collection_dir.name
        trapper_collection = rules.collection_name(research_project, collection)   # the packages, the csv and its search are by this name
        metadata, log = rules.preprocessed(deployment_id, collection, self._kept.metadata(deployment_dir), self._kept.preprocessing(deployment_dir))
        if mode != "generate" and credentials is None:
            raise UploaderError("The TRAPPER account isn't set up: save its URL, username and password in the settings.")
        deployment = self._kept.as_deployment(metadata)
        options = log.get("options", {})
        timezone_name, ignore_dst = options.get("timezone") or "UTC", bool(options.get("ignore_dst", True))
        dry = mode == "dry_run"
        site = credentials[0] if credentials else None

        # ── the research project's pk in TRAPPER ──
        project_pk: int | None
        if mode == "generate":
            project_pk = research_project.get("trapper_pk")
            if project_pk is None and credentials is not None:
                yield _step("connect", "running", "Looking for the research project's pk in TRAPPER…")
                project_pk = self.research_project_pk(credentials, research_project)
                yield _step("connect", "done", f"Research project {research_project.get('acronym')} is #{project_pk} in TRAPPER.")
            if project_pk is None:
                raise UploaderError(f"The yaml needs the research project's pk in TRAPPER, and {research_project.get('acronym')} has none yet — "
                                    "save the TRAPPER account in the settings so it can be looked up, or add the research project again from TRAPPER.")
        else:
            assert credentials is not None
            yield _step("connect", "running", "Connecting to TRAPPER…")
            project_pk = self.research_project_pk(credentials, research_project)
            yield _step("connect", "done", f"Connected — research project {research_project.get('acronym')} is #{project_pk} in TRAPPER.")

        # ── the classification project the collection goes to: the yaml's project_id ──
        classification_pk = classification_project_pk
        if credentials is not None:
            yield _step("classification", "running", "Looking for the classification project…")
            chosen = self.classification_project(credentials, project_pk, classification_project_pk)
            classification_pk = chosen["pk"]
            yield _step("classification", "done", f"The revision goes to the classification project {chosen['name']} (#{classification_pk}).")
        elif classification_pk is None:
            raise UploaderError("The yaml needs the classification project's pk in TRAPPER — choose one, which needs the TRAPPER account saved in the settings.")
        else:
            yield _step("classification", "done", f"The revision goes to the classification project #{classification_pk}.")

        location_created = deployment_created = False
        trapper_deployment_id: str | None = None   # the deployment's id as TRAPPER has it, once known

        # ── the uploader's door: found out before anything is created ──
        if mode != "generate":
            yield _step("uploader", "running", "Checking that TRAPPER's uploader accepts the account…")
            try:
                self._site.log_in_to_uploader(credentials)
            except UploaderError:
                raise
            except Exception as exc:  # noqa: BLE001
                raise UploaderError(f"Could not log in to TRAPPER's uploader: {rules.trapper_message(exc)}") from exc
            yield _step("uploader", "done", "TRAPPER's uploader accepts the account.")

        # ── what has to exist in TRAPPER ──
        deployment_url = collection_url = None   # the pages of what was sent, kept with the upload
        found = location = None
        if mode != "generate":
            assert credentials is not None
            yield _step("location", "running", f"Looking for the location {deployment.location_id} in TRAPPER…")
            if dry:
                found = self.location(credentials, project_pk, deployment)
                location_created = found is None
                note = rules.location_time_settings(found, timezone_name, ignore_dst)[2]
                yield _step("location", "done", f"Location {deployment.location_id} would be created." if location_created else
                            f"Location {deployment.location_id} is already in TRAPPER.{note}", rules.link(site, "location", (found or {}).get("pk")))
            else:
                location_created = self.ensure_location(credentials, project_pk, deployment, timezone_name, ignore_dst)
                # the package has to declare the timezone and summer-time setting of the location it goes to
                location = self.location(credentials, project_pk, deployment)
                timezone_name, ignore_dst, note = rules.location_time_settings(location, timezone_name, ignore_dst)
                yield _step("location", "done", f"Location {deployment.location_id} {'created' if location_created else 'was already in TRAPPER'}.{note}",
                            rules.link(site, "location", (location or {}).get("pk")))

            yield _step("deployment", "running", f"Looking for the deployment {deployment_id} in TRAPPER…")
            if dry:
                existing = self.deployment(credentials, project_pk, deployment)
                deployment_created = existing is None
                problem = rules.location_access_problem(found, credentials[1]) if deployment_created else None
                yield _step("deployment", "done", (f"Deployment {deployment_id} would be created." if deployment_created else
                                                   f"Deployment {deployment_id} is already in TRAPPER.") + (f" Warning: {problem}" if problem else ""),
                            rules.link(site, "deployment", (existing or {}).get("pk")))
            else:
                # not a refusal: who may use the location is a guess — it only explains a failure
                problem = rules.location_access_problem(location, credentials[1])
                try:
                    deployment_created = self.ensure_deployment(credentials, project_pk, deployment, timezone_name, ignore_dst)
                except Exception as exc:
                    if problem:
                        raise UploaderError(f"{rules.trapper_message(exc)} {problem}") from exc
                    raise
                record = self.deployment(credentials, project_pk, deployment)
                trapper_deployment_id = record["deployment_id"] if record else None
                message = f"Deployment {deployment_id} {'created' if deployment_created else 'was already in TRAPPER'}"
                if trapper_deployment_id and trapper_deployment_id != deployment_id:
                    message += f", as {trapper_deployment_id} — the package uses that id"
                deployment_url = rules.link(site, "deployment", (record or {}).get("pk"))
                yield _step("deployment", "done", message + ".", deployment_url)
        elif credentials is not None:   # only generating: what the location says is read — nothing is created
            timezone_name, ignore_dst, note = rules.location_time_settings(self.location(credentials, project_pk, deployment), timezone_name, ignore_dst)
            if note:
                yield _step("location", "done", f"Location {deployment.location_id} is in TRAPPER.{note}")

        # ── the package ──
        if dry:
            plan = self.plan(deployment_dir, log, max_zip_bytes)
            yield _step("package", "done", f"Would pack {plan['images']} image(s) into {plan['parts']} package(s) of about "
                                           f"{rules.megabytes(plan['bytes'] / plan['parts'])} MB each.")
            for name, message in [("upload", "Nothing is uploaded in a dry run."), ("process", "TRAPPER isn't asked to process anything."),
                                  ("wait", "No revision is waited for.")]:
                yield _step(name, "skipped", message)
            yield {"type": "done", "mode": mode, "collection": collection, "deployment_id": deployment_id, "would_create_location": location_created,
                   "would_create_deployment": deployment_created, "parts": plan["parts"]}
            return

        images = len(log["images"])
        if mode == "generate":
            yield _step("check", "running", f"Checking {images} image(s)…")
            self._entries(deployment_dir, log)
            yield _step("check", "done", f"{images} image(s) are there.")
        yield _step("package", "running", f"Packing {images} image(s)…")
        output_dir = packages_dir / collection
        built: list = []

        def pack(report: Callable[[dict], None]) -> None:
            def on_packed(done: int, total: int) -> None:
                if done == total or done % rules.PACK_REPORT_EVERY == 0:
                    report({"type": "pack_progress", "index": done, "total": total})
            built.append(self.build(deployment_dir, trapper_collection, deployment_id, log, project_id=classification_pk, timezone_name=timezone_name,
                                    ignore_dst=ignore_dst, trapper_deployment_id=trapper_deployment_id, output_dir=output_dir,
                                    max_zip_bytes=max_zip_bytes, progress=on_packed))

        yield from with_progress(pack)
        packages = built[0]
        package_files = [path for p in packages for path in (p.zip, p.yaml)]
        package_bytes = self._packages.size(package_files)
        packed = sum(p.files for p in packages)
        yield {"type": "package_ready", "images": packed, "parts": len(packages), "bytes": package_bytes}
        yield _step("package", "done", f"{len(packages)} package(s) of {packed} image(s).")

        csv_path = output_dir / f"{trapper_collection}{rules.DEPLOYMENTS_CSV_SUFFIX}"
        if mode == "generate":
            yield _step("csv", "running", f"Writing the deployments of {collection}…")
            csv_result = self._packages.upsert_csv(csv_path, rules.csv_row(deployment, log))
            yield _step("csv", "done", f"{Path(csv_result['path']).name}: {csv_result['action']} {deployment_id} ({csv_result['rows']} deployment(s)).")
            written = [*package_files, csv_path]
            yield {"type": "done", "mode": mode, "collection": collection, "deployment_id": deployment_id, "parts": len(packages),
                   "output_dir": str(output_dir), "files": [f.name for f in written], "images": packed, "file_sizes": self._packages.file_sizes(written)}
            return

        assert credentials is not None
        for number, package in enumerate(packages, start=1):
            yield _step("upload", "running", f"Uploading package {number} of {len(packages)}…")
            yield from with_progress(lambda report, p=package: [self._site.upload_file(credentials, path, report) for path in (p.zip, p.yaml)])
            yield _step("upload", "done", f"Package {number} of {len(packages)} uploaded.")
            yield _step("process", "running", "Asking TRAPPER to process the package…")
            try:
                self._site.process(credentials, package.yaml.name, package.zip.name, remove_zip)
            except Exception as exc:
                raise UploaderError(f"TRAPPER refused to process the package: {rules.trapper_message(exc)}") from exc
            yield _step("process", "done", "TRAPPER is processing the package.")

        yield _step("wait", "running", f"Waiting for the revision {trapper_collection} to appear in TRAPPER…")
        found_collection = self._wait_for_collection(credentials, project_pk, trapper_collection, wait_seconds, poll_seconds)
        if found_collection is None:
            raise UploaderError(f"The revision {trapper_collection} didn't appear in TRAPPER within {int(wait_seconds)} seconds — it may still be processing.")
        collection_url = rules.link(site, "collection", found_collection.get("pk"))
        yield _step("wait", "done", f"Revision {trapper_collection} is in TRAPPER.", collection_url)

        kept: list[Path] = []
        if delete_after_upload:   # what went up is on TRAPPER now
            self._packages.remove(packages, output_dir)
            self._packages.remove_from_csv(csv_path, deployment_id)
            self._packages.remove([], output_dir)
        else:
            self._packages.upsert_csv(csv_path, rules.csv_row(deployment, log))
            kept = [*package_files, csv_path]
        self._kept.mark_uploaded(deployment_dir, {
            "uploaded_at": self._now().isoformat(timespec="seconds"), "research_project_pk": project_pk, "classification_project_pk": classification_pk,
            "collection": collection, "trapper_collection": trapper_collection, "parts": len(packages), "location_created": location_created,
            "deployment_created": deployment_created, "deployment_url": deployment_url, "collection_url": collection_url,
        })
        yield {"type": "done", "mode": mode, "collection": collection, "deployment_id": deployment_id, "location_created": location_created,
               "deployment_created": deployment_created, "parts": len(packages), "images": packed, "bytes": package_bytes,
               "files_deleted": delete_after_upload,
               **({"output_dir": str(output_dir), "files": [f.name for f in kept], "file_sizes": self._packages.file_sizes(kept)} if kept else {})}

    def _wait_for_collection(self, credentials: Credentials, research_project_pk: int, name: str, timeout: float, poll: float) -> dict | None:
        """The collection, once TRAPPER has it (waiting up to `timeout` seconds), or None if it didn't appear."""
        deadline = self._monotonic() + timeout
        while True:
            found = self._site.collection(credentials, research_project_pk, name)
            if found is not None:
                return found
            if self._monotonic() >= deadline:
                return None
            self._sleep(poll)
