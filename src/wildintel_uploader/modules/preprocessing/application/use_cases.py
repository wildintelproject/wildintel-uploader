"""The use cases of the preprocessing: a deployment prepared step by step in the .staging folder of its collection — the images in parallel, each
going through the steps in their order; then the steps over all of them —, its records written beside it, and, once saved, moved to its place and
sealed. What can't be done is said before anything is written."""
from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path

from wildintel_uploader.modules.fileinfo.domain.models import IMAGE_EXTENSIONS
from wildintel_uploader.modules.fileinfo.domain.ports import FileInfoService
from wildintel_uploader.modules.preprocessing.domain.models import (
    DeploymentLike, ImageWork, PreprocessingError, PreprocessOptions, natural_key, public_record, resize_summary, zone_of,
)
from wildintel_uploader.modules.preprocessing.domain.ports import DeploymentFolders, PreprocessingService, Reports
from wildintel_uploader.modules.preprocessing.domain.steps import FolderStep, ImageStep, Job

logger = logging.getLogger(__name__)


class PreprocessingUseCases(PreprocessingService):
    """Over the steps it is given (infrastructure/steps, put together in wiring), in their order."""

    def __init__(self, info: FileInfoService, folders: DeploymentFolders, reports: Reports, *, image_steps: tuple[type[ImageStep], ...],
                 folder_steps: tuple[type[FolderStep], ...], workers: Callable[[], int], exiftool: Callable[[], str | None]) -> None:
        self._info, self._folders, self._reports = info, folders, reports
        self._image_steps, self._folder_steps = image_steps, folder_steps
        self._workers, self._exiftool = workers, exiftool

    def preprocess(self, source_dir: Path, collection_dir: Path, collection_name: str | None, deployment: DeploymentLike, options: PreprocessOptions,
                   consolidate: bool = True) -> Iterator[dict]:
        source, collection = source_dir.expanduser(), collection_dir.expanduser()
        dest = collection / deployment.deployment_id
        work = self._folders.staging(collection, deployment.deployment_id)
        self._folders.check_paths(source, dest)
        zone_of(options.timezone)
        job = Job(options=options, deployment=deployment, info=self._info, exiftool=self._exiftool())
        image_steps = [s() for s in self._image_steps if s().wanted(options)]
        folder_steps = [s() for s in self._folder_steps if s().wanted(options)]
        for step in folder_steps:
            step.check(job)
        self._folders.clear_left_pending(dest)
        self._folders.check_not_kept(dest)
        self._folders.clear_staging(work)
        # the images are prepared in .staging, on the disk of the collection, and moved to their place from there: room for all of them — as much as
        # the folder takes, at most, as resizing only makes them smaller — before anything is written
        needed = self._folders.size_of(self._folders.files(source))
        short = self._folders.shortfall(work.parent, needed, f"Preparing the images of {deployment.deployment_id}")
        if short:
            raise PreprocessingError(short)
        return self._prepare(source, collection, collection_name, dest, work, job, image_steps, folder_steps, consolidate)

    def _prepare(self, source: Path, collection: Path, collection_name: str | None, dest: Path, work: Path, job: Job, image_steps: list[ImageStep],
                 folder_steps: list[FolderStep], consolidate: bool) -> Iterator[dict]:
        deployment, options = job.deployment, job.options
        self._folders.write_collection_metadata(collection, collection_name)
        files = sorted(self._folders.files(source), key=lambda p: natural_key(p.relative_to(source)))
        images = [p for p in files if p.suffix.lower() in IMAGE_EXTENSIONS]
        image_set = set(images)
        others = [p for p in files if p not in image_set]
        total = len(files)
        cameras, _ = self._info.cameras(images)
        job = Job(options=options, deployment=deployment, info=self._info, dates=self._info.dates(images), cameras=cameras, exiftool=job.exiftool)

        def process(work_item: ImageWork) -> ImageWork:
            for step in image_steps:
                step.run(work_item, job)
            return work_item

        works: list[ImageWork] = []
        skipped: list[dict] = []
        done = 0
        self._folders.start_staging(work)
        with ThreadPoolExecutor(max_workers=self._workers()) as pool:
            futures = [(path, pool.submit(process, ImageWork(index, path, source, work))) for index, path in enumerate(images, start=1)]
            for path, future in futures:  # in order, so the events are too
                done += 1
                try:
                    prepared = future.result()
                except Exception as exc:  # one bad image doesn't stop the rest
                    logger.warning("Could not preprocess %s: %s", path, exc)
                    skipped.append({"name": str(path.relative_to(source)), "detail": str(exc)})
                    yield {"type": "skipped", "name": str(path.relative_to(source)), "detail": str(exc)}
                    continue
                works.append(prepared)
                yield {"type": "copy", "index": done, "total": total, "name": prepared.record["name"]}
        for path in others:  # anything that isn't an image goes across as it is
            self._folders.copy_as_it_is(path, work / path.relative_to(source))
            done += 1
            yield {"type": "copy", "index": done, "total": total, "name": str(path.relative_to(source))}

        for step in folder_steps:
            yield from step.run(works, job)

        records = [w.record for w in works]
        self._folders.write_images_file(work, deployment.deployment_id, works)
        self._folders.write_log(work, {"options": asdict(options), "processed": len(records), "skipped": len(skipped),
                                        "images": [public_record(r) for r in records]})
        sealed = None
        if consolidate:
            yield {"type": "sealing"}
            # from now on it is in the collection: its metadata and its seal are written there, where the seal's checks look for the rest of the project
            self._folders.publish(work, dest)
            self._folders.write_deployment_metadata(dest, deployment)
            sealed = self._folders.seal(source, dest, deployment, originals={r["name"]: r["original"] for r in records},
                                        source_hashes={r["original"]: r["source_hash"] for r in records}, preprocessing=asdict(options))
        where = dest if consolidate else work
        logger.info("Deployment %s preprocessed in %s (%d image(s), %d skipped)", deployment.deployment_id, where, len(records), len(skipped))
        report_id = None
        try:
            report_id = self._reports.preprocessing(records, skipped, deployment.deployment_id, source, dest, asdict(options))
        except Exception as exc:  # noqa: BLE001 — the import is done: not having its report is no reason to fail it
            logger.warning("Could not write the report of the preprocessing of %s: %s", deployment.deployment_id, exc)
        yield {"type": "done", "dest_dir": str(where), "processed": len(records), "skipped": len(skipped), "sealed": sealed, "report_id": report_id,
               **({"resize": resize_summary(records)} if options.resize else {})}

    def consolidate(self, source_dir: Path, collection_dir: Path, deployment: DeploymentLike) -> Iterator[dict]:
        source, collection = source_dir.expanduser(), collection_dir.expanduser()
        dest = collection / deployment.deployment_id
        work = self._folders.staging(collection, deployment.deployment_id)
        if self._folders.is_synced(dest):
            raise PreprocessingError(f"{dest.name} was synced from TRAPPER, so it can't be modified here.")
        if self._folders.is_sealed(dest):
            raise PreprocessingError(f"{dest.name} is already consolidated.")
        staged_log = self._folders.read_log(work)
        staged = staged_log is not None
        log = staged_log if staged else self._folders.read_log(dest)
        if log is None:
            raise PreprocessingError(f"{dest.name} has not been preprocessed yet.")
        if staged:
            self._folders.check_not_kept(dest)
        try:
            images, options = log["images"], log["options"]
        except (KeyError, TypeError) as exc:
            raise PreprocessingError(f"Could not read the record of the preprocessing of {dest.name}: {exc}") from exc
        return self._consolidate(source, dest, work, deployment, staged, log, images, options)

    def _consolidate(self, source: Path, dest: Path, work: Path, deployment: DeploymentLike, staged: bool, log: dict, images: list,
                     options: dict) -> Iterator[dict]:
        yield {"type": "sealing"}
        if staged:
            self._folders.publish(work, dest)
        self._folders.write_deployment_metadata(dest, deployment)
        sealed = self._folders.seal(source, dest, deployment, originals={r["name"]: r["original"] for r in images},
                                    source_hashes={r["original"]: r["source_hash"] for r in images}, preprocessing=options)
        logger.info("Deployment %s consolidated in %s", deployment.deployment_id, dest)
        yield {"type": "done", "dest_dir": str(dest), "processed": log.get("processed", len(images)), "skipped": log.get("skipped", 0), "sealed": sealed}
