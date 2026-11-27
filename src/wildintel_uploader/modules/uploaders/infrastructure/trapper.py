"""Trapper over the code of before — trapper_service, trapper_upload_service, sync_service, deployment_import_service.import_stream — and its
errors as the module's: what the client of TRAPPER says of an account or a resource, of the network, or the words of what the uploads refuse."""
from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, TypeVar

from wildintel_uploader.modules.uploaders.domain.models import (
    Account, Credentials, Forbidden, NotAuthorized, NotThere, TimedOut, Unreachable, UploaderError,
)
from wildintel_uploader.modules.uploaders.domain.ports import Deployment, KeptCollections, Trapper, UploadReports

logger = logging.getLogger(__name__)
T = TypeVar("T")


def _services():
    from wildintel_uploader.core.services import sync_service, trapper_service, trapper_upload_service
    return trapper_service, trapper_upload_service, sync_service


def _own_words(exc: Exception) -> bool:
    """Whether an error says what it is in its own words: what the uploads, the collections or the imports refuse."""
    from wildintel_uploader.core.services import deployment_import_service, trapper_upload_service
    from wildintel_uploader.shared.storage import StorageError
    return isinstance(exc, (trapper_upload_service.TrapperUploadError, StorageError, deployment_import_service.DeploymentImportError))


def as_uploader_error(exc: Exception) -> UploaderError:
    """An error of TRAPPER, of the network, or of what is asked of it, as the module's — with the words the pages have always shown."""
    import httpx
    from trapper_client import err
    if isinstance(exc, UploaderError):
        return exc
    if isinstance(exc, err.UnauthorizedError):
        return NotAuthorized("Incorrect TRAPPER username or password.")
    if isinstance(exc, err.ForbiddenError):
        return Forbidden("You don't have permission to access this TRAPPER resource.")
    if isinstance(exc, err.NotFoundError):
        return NotThere("TRAPPER resource not found.")
    if isinstance(exc, httpx.ConnectError):
        return Unreachable(f"Could not connect to the TRAPPER server: {exc}")
    if isinstance(exc, httpx.TimeoutException):
        return TimedOut(f"Timed out connecting to the TRAPPER server: {exc}")
    return UploaderError(str(exc))


def _ours(call: Callable[[], T], what: str = "A TRAPPER call") -> T:
    try:
        return call()
    except Exception as exc:  # noqa: BLE001 — every error is one of the module's
        if not isinstance(exc, UploaderError):
            from wildintel_uploader.core.logging_setup import debugging
            logger.warning("%s failed: %s", what, exc, exc_info=debugging())
        raise as_uploader_error(exc) from exc


def _told(events: Iterator[dict], what: str) -> Iterator[dict]:
    """The events of a stream; what fails mid-way is an UploaderError with the words the pages have always shown."""
    try:
        yield from events
    except Exception as exc:  # noqa: BLE001
        from wildintel_uploader.core.logging_setup import debugging
        logger.warning("%s failed: %s", what, exc, exc_info=debugging())
        raise UploaderError(str(exc) if _own_words(exc) else as_uploader_error(exc).message) from exc


class TrapperClient(Trapper):
    def credentials(self, account: Account) -> Credentials:
        try:
            return _services()[0].resolve_credentials(account.url, account.username, account.password)
        except ValueError as exc:
            raise UploaderError(str(exc)) from exc

    def defaults(self) -> dict:
        return _services()[0].get_connection_defaults()

    def keep_account(self, credentials: Credentials) -> None:
        _services()[0].save_credentials(*credentials)

    def ask(self, what: str, credentials: Credentials, *args: Any) -> Any:
        return _ours(lambda: getattr(_services()[0], what)(*credentials, *args), "Trapper call")

    def find_research_project(self, credentials: Credentials, record: dict) -> int:
        return _ours(lambda: _services()[1].find_research_project(credentials, record), "Reading the classification projects")

    def check_selection(self, credentials: Credentials, record: dict, collection: str | None, describe: Callable[[Exception], str]) -> list[dict]:
        return _services()[1].check_selection(credentials, record, collection, describe=describe)

    def check_access(self, credentials: Credentials, record: dict, location_ids: list[str], classification_project_pk: int | None,
                     describe: Callable[[Exception], str]) -> list[dict]:
        return _services()[1].check_access(credentials, record, location_ids, classification_project_pk=classification_project_pk, describe=describe)

    def upload(self, credentials: Credentials | None, record: dict, collection_dir: Path, deployment_id: str, mode: str, classification_project_pk: int | None,
               delete_files: bool) -> Iterator[dict]:
        from wildintel_uploader.core import config
        return _services()[1].upload_stream(credentials, record, collection_dir, deployment_id, config.packages_dir() / record["acronym"], mode=mode,
                                            max_zip_bytes=config.max_zip_mb() * 1024 * 1024, classification_project_pk=classification_project_pk,
                                            delete_after_upload=delete_files)

    def import_deployment(self, credentials: Credentials, research_project_pk: int, classification_project_pk: int | None, source_dir: str, deployment: Deployment,
                          timezone: str | None, research_project_id: str | None, ignore_dst: bool, register: bool) -> Iterator[dict]:
        from wildintel_uploader.core.services import deployment_import_service
        try:
            events = deployment_import_service.import_stream(*credentials, research_project_pk, classification_project_pk, source_dir, deployment, timezone,
                                                             research_project_id=research_project_id, ignore_dst=ignore_dst, register=register)
        except deployment_import_service.DeploymentImportError as exc:
            raise UploaderError(str(exc)) from exc
        return _told(events, "Deployment import")

    def collection_names(self, credentials: Credentials, research_project_pk: int, classification_project_pk: int) -> list[dict]:
        return _ours(lambda: _services()[2].collections_with_deployments(credentials, research_project_pk, classification_project_pk),
                     "Reading the collections of the classification project")

    def sync(self, credentials: Credentials, project: dict, classification_project_pk: int, collections: list[str], deployments: list[str] | None,
             download_images: bool) -> Iterator[dict]:
        from wildintel_uploader.core import config
        events = _services()[2].sync_stream(credentials, config.collections_dir(), project, classification_project_pk, collections, deployments, download_images)
        return _told(events, "Syncing the local collections")

    def describe(self, exc: Exception) -> str:
        from wildintel_uploader.core.logging_setup import debugging
        logger.warning("A TRAPPER check failed: %s", exc, exc_info=debugging())
        return str(exc) if _own_words(exc) or isinstance(exc, UploaderError) else as_uploader_error(exc).message


class CollectionsFolder(KeptCollections):
    @staticmethod
    def _lfs():
        from wildintel_uploader.core.services import local_folder_service
        return local_folder_service

    @staticmethod
    def _root() -> Path:
        from wildintel_uploader.core import config
        return config.collections_dir()

    def _failed(self, call: Callable[[], T]) -> T:
        try:
            return call()
        except self._lfs().LocalFolderError as exc:
            raise UploaderError(str(exc)) from exc

    def project(self, project: str) -> dict | None:
        return self._failed(lambda: {p["acronym"]: p for p in self._lfs().list_research_projects(self._root())}.get(project))

    def collection_dir(self, project: str, collection: str) -> Path:
        return self._failed(lambda: self._lfs().project_dir(self._root(), project) / collection)

    def collections(self, project: str) -> list[dict]:
        return self._failed(lambda: _services()[1].list_collections(self._root(), project))

    def location_of(self, collection_dir: Path, deployment_id: str) -> str | None:
        metadata = _services()[1]._read_json(collection_dir / deployment_id / self._lfs().DEPLOYMENT_METADATA_FILE)
        return metadata.get("location_id") if isinstance(metadata, dict) else None

    def location_time(self, project: str, location_id: str | None) -> dict:
        return self._failed(lambda: self._lfs().location_time(self._root(), project, location_id))

    def check_project_dir(self, project: str) -> None:
        self._failed(lambda: self._lfs().project_dir(self._root(), project))

    def note_failure(self, project: str, deployment_id: str, destination: str, note: str | None) -> None:
        try:
            self._lfs().set_upload_failure(self._root(), project, deployment_id, destination, note)
        except self._lfs().LocalFolderError:
            pass


class SavedUploadReports(UploadReports):
    def upload(self, collection: str, project: str, items: list[dict], started_at: str, finished_at: str) -> str | None:
        from wildintel_uploader.core.services import report_service
        return report_service.save(report_service.upload_report(collection, project, items, started_at=started_at, finished_at=finished_at))
