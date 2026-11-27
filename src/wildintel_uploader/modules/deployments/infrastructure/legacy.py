"""The ports of the deployments over the code of before: the collections folder (its collections, the seal of what it keeps), how a collection
holds its deployments, the photos (deployment_photos) and the import sessions. What they refuse is the deployments', with their words."""
from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TypeVar

from wildintel_uploader.modules.deployments.application.imports import Importing
from wildintel_uploader.modules.deployments.application.seal import Sealing
from wildintel_uploader.modules.deployments.domain.models import DeploymentMissing, DeploymentsFailed
from wildintel_uploader.modules.deployments.domain.ports import (
    CollectionLayout, Deployment, Folders, ImportSessions, Photos,
)
from wildintel_uploader.modules.deployments.infrastructure import collections as layout
from wildintel_uploader.modules.settings.domain.ports import StoredSettings
from wildintel_uploader.modules.catalog.domain.ports import CatalogService

T = TypeVar("T")


@contextmanager
def _failed() -> Iterator[None]:
    from wildintel_uploader.shared.storage import StorageError
    try:
        yield
    except StorageError as exc:
        raise DeploymentsFailed(str(exc)) from exc


def _root() -> Path:
    from wildintel_uploader.modules.deployments.infrastructure.plugs import config
    return config.collections_dir()


class CollectionFolders(Folders):
    def __init__(self, settings: StoredSettings, catalog_of: Callable[[Path], CatalogService], sealing: Callable[[], Sealing]) -> None:
        self._settings, self._catalog_of, self._sealing = settings, catalog_of, sealing   # the catalog of a collections folder, through its contract

    def root(self) -> Path:
        return self._settings.collections_dir()

    def check_collection(self, folder: Path) -> dict:
        return layout.check_collection(folder)

    def local_deployments(self, folder: Path) -> list[dict]:
        return layout.list_deployments(folder)

    def imported(self, project: str, exclude_deployment: str | None) -> dict[str, list[dict]]:
        with _failed():
            return layout.imported_source_hashes(self.root(), project, exclude_deployment)

    def seal_status(self, folder: Path) -> dict:
        return self._sealing().verify(folder)

    def location_time(self, project_dir: Path, location_id: str | None) -> dict:
        from wildintel_uploader.modules.catalog.domain.models import CatalogError
        try:   # the research project of that folder, in the catalog of its collections folder — through its contract
            return self._catalog_of(project_dir.parent).location_time(project_dir.name, location_id)
        except CatalogError as exc:
            raise DeploymentsFailed(exc.message) from exc


class DeploymentPhotos(Photos):
    @staticmethod
    def _missing(call: Callable[[], T]) -> T:
        from wildintel_uploader.modules.deployments.infrastructure import deployment_photos
        try:
            return call()
        except deployment_photos.DeploymentPhotosError as exc:
            raise DeploymentMissing(str(exc)) from exc

    def list(self, project: str, collection: str, deployment_id: str) -> list[dict]:
        from wildintel_uploader.modules.deployments.infrastructure import deployment_photos
        return self._missing(lambda: deployment_photos.list_photos(_root(), project, collection, deployment_id))

    def jpeg(self, project: str, collection: str, deployment_id: str, name: str, large: bool) -> bytes:
        from wildintel_uploader.modules.deployments.infrastructure import deployment_photos
        size = deployment_photos.LARGE if large else deployment_photos.THUMBNAIL
        return self._missing(lambda: deployment_photos.photo_jpeg(_root(), project, collection, deployment_id, name, size))


class StoredSessions(ImportSessions):
    """Over session_store: a file a session, in the app's data."""

    @staticmethod
    def _store():
        from wildintel_uploader.modules.deployments.infrastructure import session_store
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


class LayoutOfTheCollections(CollectionLayout):
    """How a collection holds its deployments: the paths, what is kept and the seal as an import says (application.imports), the files as the
    collections folder keeps them, the room on the disk."""

    def __init__(self, importing: Callable[[], Importing]) -> None:
        self._importing = importing

    def check_paths(self, source: Path, dest: Path) -> None:
        self._importing().check_paths(source, dest)

    def is_pending(self, dest: Path) -> bool:
        return self._importing().is_pending(dest)

    def check_not_kept(self, dest: Path) -> None:
        self._importing().check_not_kept(dest)

    def is_synced(self, dest: Path) -> bool:
        return layout.is_synced(dest)

    def shortfall(self, folder: Path, needed: int, what: str, where: str) -> str | None:
        from wildintel_uploader.modules.deployments.infrastructure import disk_space
        return disk_space.shortfall(folder, needed, what, where)

    def write_collection_metadata(self, collection: Path, name: str | None) -> None:
        layout.write_collection_metadata(collection, name)

    def image_entry(self, name: str, local_time: str | None, source: str, extra: dict) -> dict:
        return layout.image_entry(name, local_time, source, extra)

    def write_images_file(self, folder: Path, deployment_id: str, images: list[dict], source: str = "local") -> None:
        layout.write_images_file(folder, deployment_id, images, source=source)

    def write_deployment_metadata(self, dest: Path, deployment: dict) -> None:
        layout.write_deployment_metadata(dest, deployment)

    def seal(self, source: Path, dest: Path, deployment: Deployment, **details) -> bool:
        return self._importing().seal(source, dest, deployment, **details)
