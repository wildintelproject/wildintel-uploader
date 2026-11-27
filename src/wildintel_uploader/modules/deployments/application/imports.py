"""Bringing a folder of camera-trap images into a collection: what a folder or a session folder holds, what the deployment form starts from, what
the collection's logs say of a deployment, where it is kept, and the folder copied — organized for the preprocessing, or as it is, with its
metadata, then sealed. The rules are the domain's (domain.imports); the folders, what is known of the images (modules.fileinfo) and the seal are
what it is given."""
from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from pathlib import Path

from wildintel_uploader.modules.deployments.application.seal import Sealing
from wildintel_uploader.modules.deployments.domain import imports as rules
from wildintel_uploader.modules.deployments.domain.models import DeploymentImportError, DeploymentsFailed
from wildintel_uploader.modules.deployments.domain.naming import natural_key
from wildintel_uploader.modules.deployments.domain.ports import Deployment, ImportFolder
from wildintel_uploader.modules.fileinfo.domain.ports import FileInfoService
from wildintel_uploader.shared.storage import StorageError

logger = logging.getLogger(__name__)


class Importing:
    """`exif_fields` says the EXIF fields the checks ask, as the settings have them."""

    def __init__(self, folder: ImportFolder, files: Callable[[], FileInfoService], sealing: Callable[[], Sealing],
                 exif_fields: Callable[[], list[str]] = list) -> None:
        self._folder, self._files, self._sealing, self._exif_fields = folder, files, sealing, exif_fields

    def _images(self, folder: Path) -> tuple[list[Path], list[Path]]:
        files = self._folder.files(folder)
        return files, [p for p in files if rules.is_image(p)]

    def _a_folder(self, folder: Path) -> None:
        if not self._folder.is_dir(folder):
            raise rules.not_a_folder(folder)

    # ── a folder of images ──

    def scan_folder(self, folder: Path) -> dict:
        """What a folder holds, and nothing more: how many files, and how many of them are images (by their extension). Reading the images is the
        job of what follows. DeploymentImportError when it is not a folder."""
        self._a_folder(folder)
        files, images = self._images(folder)
        return rules.scan(len(files), len(images))

    def prefetch(self, folder: Path) -> None:
        """Starts reading the EXIF of a folder's images in the background — what the checks, the details and the preprocessing will ask —, right
        after it is scanned. Nothing happens if it is not a folder."""
        if self._folder.is_dir(folder):
            self._files().prefetch(self._images(folder)[1], rules.extra_fields(self._exif_fields()))

    def guess_details(self, folder: Path) -> dict:
        """The deployment form's starting point, read from the images' metadata (domain.imports.guess). DeploymentImportError when it is not a
        folder."""
        self._a_folder(folder)
        _, images = self._images(folder)
        dates = self._files().dates(images)
        cameras, reader = self._files().cameras(images)
        return rules.guess([dates.get(p) for p in images], [cameras[p].model for p in images], [cameras[p].camera_id for p in images], reader)

    def scan_session(self, folder: Path) -> dict:
        """A session folder — one subfolder per deployment — scanned: each subfolder's own scan, named after it (hidden ones are left out), and
        how many loose files sit beside them. When the folder holds a <collection>_FileTimestampLog.csv, the subfolders it has a row for have its
        start and end (domain.imports.match_log), and "timestamp_log" says {"name", "path", "rows", "matched", "unmatched", "revision"}; None when
        there is no usable log.

        Raises:
            DeploymentImportError: it is not a folder, or has no subfolders."""
        self._a_folder(folder)
        subfolders = self._folder.subfolders(folder)
        if not subfolders:
            raise rules.no_subfolders()
        names = self._folder.loose(folder)
        loose = sum(1 for n in names if not rules.is_timestamp_log(n))   # a timestamp log is not a stray file
        warnings = rules.loose_warnings(loose)
        deployments = [rules.session_deployment(p.name, str(p), self.scan_folder(p)) for p in subfolders]
        log_name, log_warnings = rules.timestamp_log_of(folder.name, names)
        warnings += log_warnings
        timestamp_log = None
        if log_name is not None:
            log = folder / log_name
            try:
                found, log_warnings = rules.periods(log_name, self._folder.timestamp_rows(log))
            except StorageError as exc:
                found, log_warnings = {}, rules.unreadable_log(exc)
            warnings += log_warnings
            timestamp_log = {"name": log_name, "path": str(log), **rules.match_log(deployments, found)}
        return {"deployments": deployments, "loose_files": loose, "warnings": warnings, "timestamp_log": timestamp_log}

    # ── where a deployment is kept ──

    def default_collection(self, project: str, deployment_id: str) -> Path:
        """<collections folder>/<research project id>/<R0003>. DeploymentImportError when the ids can't name it."""
        return Path(rules.collection_of(self._folder.root(), project, deployment_id))

    def is_pending(self, dest: Path) -> bool:
        return rules.is_pending(self._folder.has(dest, rules.PREPROCESSING_LOG_FILE), self._folder.has(dest, rules.SEAL_FILE))

    def kept(self, project: str, deployment_id: str) -> Path | None:
        """The folder where this deployment is already kept, with something in it — when importing it again would be refused. None otherwise, or
        when the ids can't name a folder."""
        try:
            dest = self.default_collection(project, deployment_id) / deployment_id
        except DeploymentImportError:
            return None
        return dest if self._folder.has_content(dest) and not self.is_pending(dest) else None

    def check_not_kept(self, dest: Path) -> None:
        rules.check_not_kept(dest, self._folder.synced(dest), self._folder.has_content(dest))

    def check_paths(self, source: Path, dest: Path) -> None:
        """DeploymentImportError: the source is not a folder, or the destination is the source or inside it."""
        self._a_folder(source)
        rules.check_nesting(self._folder.resolve(source), self._folder.resolve(dest))

    def log_entry(self, project: str, deployment_id: str) -> dict:
        """What the collection's two logs say of a deployment (domain.imports.log_entry). DeploymentsFailed when a log can't be read."""
        collection = self.default_collection(project, deployment_id)
        try:
            timestamps = self._folder.timestamp_rows(collection / rules.timestamp_log_name(collection.name))
            fieldwork = self._folder.fieldwork_rows(collection)
        except StorageError as exc:
            raise DeploymentsFailed(str(exc)) from exc
        return rules.log_entry(collection.name, deployment_id, timestamps, fieldwork)

    # ── the copy ──

    def copy_folder(self, source: Path, dest: Path) -> Iterator[dict]:
        """Copies the source's files into dest, keeping its subfolders — never touching the source. "copy" as each file is done."""
        files = self._folder.files(source)
        for index, path in enumerate(files, start=1):
            relative = path.relative_to(source)
            self._folder.copy(path, dest / relative)
            yield rules.copied(index, len(files), str(relative))

    def organize(self, project: str, source_dir: str, deployment: Deployment) -> tuple[Path, Iterator[dict]]:
        """The source's images under <collections folder>/<research project>/<collection>/<deployment id>, with the collection's and the
        deployment's metadata beside them — what the preprocessing starts from. Where they go, and the events of the copy.

        Raises:
            DeploymentImportError: bad paths — checked before anything is copied."""
        source = Path(source_dir).expanduser()
        collection = self.default_collection(project, deployment.deployment_id)
        dest = collection / deployment.deployment_id
        self.check_paths(source, dest)

        def events() -> Iterator[dict]:
            self._folder.write_collection(collection, collection.name)
            yield from self.copy_folder(source, dest)
            self._folder.write_deployment(dest, deployment.model_dump())

        return dest, events()

    def images_info(self, dest: Path) -> list[tuple[str, str | None, dict]]:
        """The images of a copied deployment, in natural order, as images.json keeps them: the name, the camera's wall clock (None when the EXIF
        has none) and, as extras, the camera and its id, the size and the pixels — so that what comes after does not read the images again."""
        ordered = sorted((p for p in self._folder.files(dest) if rules.is_image(p)), key=lambda p: natural_key(p.relative_to(dest)))
        dates = self._files().dates(ordered)
        cameras, _ = self._files().cameras(ordered)   # read with the dates: no other run
        entries = []
        for path in ordered:
            taken = dates.get(path)
            width, height = self._folder.dimensions(path)
            entries.append((str(path.relative_to(dest)), taken.isoformat() if taken else None,
                            {"camera": cameras[path].model, "camera_id": cameras[path].camera_id, "width": width, "height": height,
                             "size_bytes": self._folder.size(path)}))
        return entries

    def seal(self, source: Path, dest: Path, deployment: Deployment, **details) -> bool:
        """Checks the source images and seals the deployment kept in dest. A failure is logged and the deployment is left without a seal — it was
        imported all the same — and False says so."""
        try:
            self._sealing().seal(source, dest, deployment, **details)
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not seal %s: %s", deployment.deployment_id, exc, exc_info=True)
            return False

    def copy_as_it_is(self, source_dir: str, collection_dir: str, collection_name: str | None, deployment: Deployment) -> Iterator[dict]:
        """The source's images under collection_dir/<deployment id>, with the collection's and the deployment's metadata, then sealed: "copy" as
        each file is done, "sealing", and "done" with where it is and whether it was sealed.

        Raises:
            DeploymentImportError: bad paths, or the deployment is already kept — checked before anything is copied."""
        source = Path(source_dir).expanduser()
        collection = Path(collection_dir).expanduser()
        dest = collection / deployment.deployment_id
        self.check_paths(source, dest)
        self.check_not_kept(dest)

        def events() -> Iterator[dict]:
            self._folder.write_collection(collection, collection_name)
            yield from self.copy_folder(source, dest)
            self._folder.write_deployment(dest, deployment.model_dump())
            self._folder.write_images(dest, deployment.deployment_id, self.images_info(dest))
            yield {"type": "sealing"}
            sealed = self.seal(source, dest, deployment)
            logger.info("Deployment %s organized locally in %s", deployment.deployment_id, dest)
            yield {"type": "done", "dest_dir": str(dest), "sealed": sealed}

        return events()
