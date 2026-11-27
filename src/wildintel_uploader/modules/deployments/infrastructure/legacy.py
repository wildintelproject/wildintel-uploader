"""The ports of the deployments over the code of before: the memory cards (card_copy_service), the folders and the collections
(deployment_import_service, local_folder_service, seal_service), the revisions (statistics_service), the photos (deployment_photos). What they
refuse is the deployments', with their words."""
from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TypeVar

from wildintel_uploader.modules.deployments.domain.models import DeploymentMissing, DeploymentsFailed
from wildintel_uploader.modules.deployments.domain.ports import Cards, CollectionStatistics, Deployment, Folders, ImportSessions, Photos, Repairs, Revisions
from wildintel_uploader.modules.deployments.infrastructure import collections as layout

T = TypeVar("T")


@contextmanager
def _failed() -> Iterator[None]:
    from wildintel_uploader.core.services import deployment_import_service as dis
    from wildintel_uploader.shared.storage import StorageError
    try:
        yield
    except (dis.DeploymentImportError, StorageError) as exc:
        raise DeploymentsFailed(str(exc)) from exc


def _root() -> Path:
    from wildintel_uploader.core import config
    return config.collections_dir()


class MemoryCards(Cards):
    @staticmethod
    def _cards():
        from wildintel_uploader.core.services import card_copy_service
        return card_copy_service

    def copy(self, path: str) -> Iterator[dict]:
        return self._cards().copy_card(path)

    def eject(self, path: str) -> dict:
        return self._cards().eject(path)

    def discard(self, path: str) -> bool:
        return self._cards().discard(path)


class CollectionFolders(Folders):
    @staticmethod
    def _dis():
        from wildintel_uploader.core.services import deployment_import_service
        return deployment_import_service

    @staticmethod
    def _lfs():
        from wildintel_uploader.core.services import local_folder_service
        return local_folder_service

    def root(self) -> Path:
        return _root()

    def scan(self, folder: Path) -> dict:
        with _failed():
            return self._dis().scan_folder(folder)

    def read_ahead(self, folder: Path) -> None:
        from wildintel_uploader.core import config
        self._dis().prefetch_metadata(folder, config.load_settings().VALIDATION.exif_fields)

    def guess(self, folder: Path) -> dict:
        with _failed():
            return self._dis().guess_details(folder)

    def scan_session(self, folder: Path) -> dict:
        with _failed():
            return self._dis().scan_session(folder)

    def check_collection(self, folder: Path) -> dict:
        return self._lfs().check_collection(folder)

    def default_collection(self, project: str, deployment_id: str) -> Path:
        with _failed():
            return self._dis().default_collection_dir(project, deployment_id)

    def kept(self, project: str, deployment_id: str) -> Path | None:
        return self._dis().existing_deployment_dir(project, deployment_id)

    def local_deployments(self, folder: Path) -> list[dict]:
        return self._lfs().list_deployments(folder)

    def log_entry(self, project: str, deployment_id: str) -> dict:
        with _failed():
            return self._dis().log_entry(project, deployment_id)

    def seal_status(self, folder: Path) -> dict:
        from wildintel_uploader.core.services import seal_service
        return seal_service.verify(folder)

    def location_time(self, project_dir: Path, location_id: str | None) -> dict:
        with _failed():
            return self._lfs().location_time_in(project_dir, location_id)

    def copy_as_it_is(self, source_dir: str, collection_dir: str, collection_name: str | None, deployment: Deployment) -> Iterator[dict]:
        with _failed():
            return self._dis().import_local_stream(source_dir, collection_dir, collection_name, deployment)

    def organize(self, research_project_id: str, source_dir: str, deployment: Deployment) -> tuple[Path, Iterator[dict]]:
        with _failed():
            return self._dis().organize_stream(research_project_id, source_dir, deployment)


class KeptRevisions(Revisions):
    def previous(self, project: str, deployment_id: str) -> dict | None:
        from wildintel_uploader.core.services import statistics_service
        return statistics_service.previous_deployment(_root(), project, deployment_id)

    def next(self, project: str, location_id: str) -> dict:
        from wildintel_uploader.core.services import statistics_service
        return statistics_service.next_revision(_root(), project, location_id)

    def before(self, project: str, deployment_id: str) -> list[dict]:
        from wildintel_uploader.core.services import statistics_service
        return [{"revision": r.revision, "deployment_id": r.deployment_id, "image_count": r.times.image_count, "times": list(r.times.times)}
                for r in statistics_service.revisions_before(_root(), project, deployment_id)]


class DeploymentPhotos(Photos):
    @staticmethod
    def _missing(call: Callable[[], T]) -> T:
        from wildintel_uploader.core.services import deployment_photos
        try:
            return call()
        except deployment_photos.DeploymentPhotosError as exc:
            raise DeploymentMissing(str(exc)) from exc

    def list(self, project: str, collection: str, deployment_id: str) -> list[dict]:
        from wildintel_uploader.core.services import deployment_photos
        return self._missing(lambda: deployment_photos.list_photos(_root(), project, collection, deployment_id))

    def jpeg(self, project: str, collection: str, deployment_id: str, name: str, large: bool) -> bytes:
        from wildintel_uploader.core.services import deployment_photos
        size = deployment_photos.LARGE if large else deployment_photos.THUMBNAIL
        return self._missing(lambda: deployment_photos.photo_jpeg(_root(), project, collection, deployment_id, name, size))


class KeptRepairs(Repairs):
    @staticmethod
    def _repair():
        from wildintel_uploader.core.services import repair_service
        return repair_service

    def collections(self, project: str) -> list[dict]:
        rs = self._repair()
        try:
            return rs.list_collections(_root(), project)
        except rs.RepairError as exc:
            raise DeploymentsFailed(str(exc)) from exc

    def inspect(self, project: str, collection: str, deployment_id: str) -> dict:
        rs = self._repair()
        try:
            return rs.inspect(_root(), project, collection, deployment_id)
        except rs.RepairError as exc:
            raise DeploymentMissing(str(exc)) from exc

    def repair(self, project: str, collection: str, deployment_id: str) -> Iterator[dict]:
        """What fails mid-way says so with its words — what the repair itself refuses as it was, anything else as "The repair failed: …"."""
        from wildintel_uploader.core.services import deployment_import_service
        rs = self._repair()
        try:
            events = rs.repair_stream(_root(), project, collection, deployment_id)
        except rs.RepairError as exc:
            raise DeploymentsFailed(str(exc)) from exc

        def told() -> Iterator[dict]:
            try:
                yield from events
            except (rs.RepairError, layout.LocalFolderError, deployment_import_service.DeploymentImportError) as exc:
                raise DeploymentsFailed(str(exc)) from exc
            except Exception as exc:  # noqa: BLE001
                raise DeploymentsFailed(f"The repair failed: {exc}") from exc
        return told()


class KeptStatistics(CollectionStatistics):
    def revision(self, project: str, collection: str) -> list[dict]:
        from wildintel_uploader.core import config
        from wildintel_uploader.core.services import deployment_import_service, statistics_service
        settings = config.load_settings()
        post = settings.POSTVALIDATION
        try:
            return statistics_service.collection_statistics(
                config.collections_dir(settings), project, collection, sequence_gap_seconds=post.sequence_gap_seconds, min_revisions=post.min_revisions,
                method=post.similarity_method, tolerances={"image_count": post.image_count_tolerance, "sequence_count": post.sequence_count_tolerance,
                                                           "sequence_length": post.sequence_length_tolerance})
        except deployment_import_service.DeploymentImportError as exc:
            raise DeploymentMissing(str(exc)) from exc

    def compare(self, project: str, first: str, second: str) -> dict:
        from wildintel_uploader.core import config
        from wildintel_uploader.core.services import statistics_service
        settings = config.load_settings()
        with _failed():
            return statistics_service.compare_deployments(config.collections_dir(settings), project, first, second,
                                                          sequence_gap_seconds=settings.POSTVALIDATION.sequence_gap_seconds)


class StoredSessions(ImportSessions):
    """Over session_store: a file a session, in the app's data."""

    @staticmethod
    def _store():
        from wildintel_uploader.core.services import session_store
        return session_store

    def list(self) -> list[dict]:
        return self._store().list_sessions()

    def save_scan(self, task_id: str | None, source_dir: str, scan: dict) -> dict:
        store = self._store()
        try:
            return store.write_scan_phase(task_id, source_dir=source_dir, scan=scan)
        except store.InvalidTaskId as exc:
            raise DeploymentsFailed(str(exc)) from exc

    def save_selection(self, task_id: str, selection: dict) -> dict:
        try:
            return self._store().write_selection_phase(task_id, selection=selection)
        except LookupError as exc:
            raise DeploymentMissing(str(exc)) from exc

    def save_details(self, task_id: str, deployment: dict) -> dict:
        try:
            return self._store().write_details_phase(task_id, deployment=deployment)
        except LookupError as exc:
            raise DeploymentMissing(str(exc)) from exc

    def discard(self, task_id: str) -> None:
        store = self._store()
        try:
            store.discard_session(task_id)
        except store.InvalidTaskId as exc:
            raise DeploymentsFailed(str(exc)) from exc
