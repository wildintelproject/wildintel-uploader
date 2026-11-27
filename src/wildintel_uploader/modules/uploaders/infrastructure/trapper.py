"""TRAPPER for the uploaders — the account, as the settings keep it; what TRAPPER has, through its API (TrapperSite); a deployment
registered from the wizard — and its errors as the module's: what the client of TRAPPER says of an account or a resource,
of the network, or the words of what the uploads refuse. And the research projects and the collections kept in the collections folder."""
from __future__ import annotations

import logging
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

from wildintel_uploader.modules.uploaders.domain.models import (
    Account, Credentials, Forbidden, NotAuthorized, NotThere, TimedOut, Unreachable, UploaderError,
)
from wildintel_uploader.modules.deployments.domain.naming import DEPLOYMENT_METADATA_FILE
from wildintel_uploader.modules.reports.domain.ports import ReportsService
from wildintel_uploader.modules.uploaders.infrastructure.failures import UploadFailures
from wildintel_uploader.modules.uploaders.infrastructure.packages import UPLOAD_LOG_FILE, read_json, size_of
from wildintel_uploader.modules.preprocessing.domain.models import PREPROCESSING_LOG_FILE
from wildintel_uploader.shared.storage import StorageError, valid_project_id
from wildintel_uploader.modules.uploaders.domain.ports import Deployment, KeptCollections, Trapper, TrapperSite, UploadPlaces, UploadReports
from wildintel_uploader.modules.catalog.domain.models import CatalogError
from wildintel_uploader.modules.catalog.domain.ports import CatalogService

logger = logging.getLogger(__name__)
T = TypeVar("T")


def _own_words(exc: Exception) -> bool:
    """Whether an error says what it is in its own words: what the uploads, the collections or the imports refuse."""
    from wildintel_uploader.modules.deployments.domain.models import DeploymentsError
    from wildintel_uploader.shared.storage import StorageError
    return isinstance(exc, (StorageError, DeploymentsError))


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
            from wildintel_uploader.shared.logs import debugging
            logger.warning("%s failed: %s", what, exc, exc_info=debugging())
        raise as_uploader_error(exc) from exc


class TrapperClient(Trapper):
    """`trapper` gives the TRAPPER section of the settings, asked each time, and `keep_account` keeps an account in it; `site` is TRAPPER's API."""

    def __init__(self, trapper: Callable[[], Any], keep_account: Callable[[Credentials], None], site: TrapperSite) -> None:
        self._trapper, self._keep_account, self._site = trapper, keep_account, site

    def credentials(self, account: Account) -> Credentials:
        """The account, completed from the settings — what is still missing named."""
        trapper = self._trapper()
        resolved = (account.url or trapper.base_url, account.username or trapper.user_name, account.password or trapper.user_password)
        missing = [name for name, value in zip(("URL", "username", "password"), resolved) if not value]
        if missing:
            raise UploaderError(f"Missing TRAPPER {', '.join(missing)} — provide it, or save it in the configuration first.")
        return resolved  # type: ignore[return-value]

    def defaults(self) -> dict:
        trapper = self._trapper()
        return {"base_url": trapper.base_url, "user_name": trapper.user_name, "has_password": bool(trapper.user_password)}

    def keep_account(self, credentials: Credentials) -> None:
        self._keep_account(credentials)

    def test_connection(self, credentials: Credentials) -> dict:
        return _ours(lambda: self._site.test_connection(credentials), "Trapper call")

    def research_projects(self, credentials: Credentials) -> list[dict]:
        return _ours(lambda: self._site.research_projects(credentials), "Trapper call")

    def classification_projects(self, credentials: Credentials, research_project_pk: int) -> list[dict]:
        return _ours(lambda: self._site.classification_projects(credentials, research_project_pk), "Trapper call")

    def locations(self, credentials: Credentials, research_project_pk: int) -> list[dict]:
        return _ours(lambda: self._site.locations(credentials, research_project_pk), "Trapper call")

    def deployments(self, credentials: Credentials, research_project_pk: int) -> list[dict]:
        return _ours(lambda: self._site.deployments(credentials, research_project_pk), "Trapper call")

    def register(self, credentials: Credentials, research_project_pk: int, classification_project_pk: int | None, deployment: Deployment, timezone: str,
                 ignore_dst: bool) -> None:
        _ours(lambda: self._site.register(credentials, research_project_pk, classification_project_pk, deployment, timezone, ignore_dst),
              "Registering the deployment")

    def failure(self, exc: Exception) -> UploaderError:
        """An error of TRAPPER, of the network or of what is asked of it, as the module's — logged when it is not one of its own."""
        if not isinstance(exc, UploaderError):
            from wildintel_uploader.shared.logs import debugging
            logger.warning("A TRAPPER call failed: %s", exc, exc_info=debugging())
        return as_uploader_error(exc)

    def describe(self, exc: Exception) -> str:
        from wildintel_uploader.shared.logs import debugging
        logger.warning("A TRAPPER check failed: %s", exc, exc_info=debugging())
        return str(exc) if _own_words(exc) or isinstance(exc, UploaderError) else as_uploader_error(exc).message


class CollectionsFolder(KeptCollections):
    def __init__(self, root: Callable[[], Path], catalog_of: Callable[[Path], CatalogService], failures: UploadFailures) -> None:
        self._root_dir, self._catalog_of, self._failures = root, catalog_of, failures   # the catalog of a collections folder, through its contract

    def _catalog(self) -> CatalogService:
        return self._catalog_of(self._root())

    def _root(self) -> Path:
        return self._root_dir()

    def _failed(self, call: Callable[[], T]) -> T:
        try:
            return call()
        except StorageError as exc:
            raise UploaderError(str(exc)) from exc
        except CatalogError as exc:
            raise UploaderError(exc.message) from exc

    def project(self, project: str) -> dict | None:
        """What an upload needs of a research project kept: its acronym, its name and its pk in TRAPPER."""
        found = self._failed(lambda: next((p for p in self._catalog().projects() if p.acronym == project), None))
        return {"acronym": found.acronym, "name": found.name, "trapper_pk": found.trapper_pk} if found is not None else None

    def collection_dir(self, project: str, collection: str) -> Path:
        return self._failed(lambda: (self._root() / valid_project_id(project)) / collection)

    def collections(self, project: str) -> list[dict]:
        return self._failed(lambda: list_collections(self._root(), project))

    def location_of(self, collection_dir: Path, deployment_id: str) -> str | None:
        metadata = read_json(collection_dir / deployment_id / DEPLOYMENT_METADATA_FILE)
        return metadata.get("location_id") if isinstance(metadata, dict) else None

    def location_time(self, project: str, location_id: str | None) -> dict:
        return self._failed(lambda: self._catalog().location_time(project, location_id))

    def check_project_dir(self, project: str) -> None:
        self._failed(lambda: (self._root() / valid_project_id(project)))

    def note_failure(self, project: str, deployment_id: str, destination: str, note: str | None) -> None:
        try:
            self._failures.note(project, deployment_id, destination, note)
        except StorageError:
            pass


class SavedUploadReports(UploadReports):
    """Through the contract of the reports."""

    def __init__(self, reports: ReportsService) -> None:
        self._reports = reports

    def upload(self, collection: str, project: str, items: list[dict], started_at: str, finished_at: str) -> str | None:
        return self._reports.save_upload(collection, project, items, started_at, finished_at)


_COLLECTION_RE = re.compile(r"^R\d{4}(_.+)?$")
_DEPLOYMENT_RE = re.compile(r"^R\d{4}-.+$")


def list_collections(collections_dir: Path, research_project_id: str) -> list[dict]:
    """The collections kept for a research project, and the deployments in each: how many images, whether it was preprocessed (a requirement) and
    whether it was uploaded."""
    project = collections_dir / valid_project_id(research_project_id)
    if not project.is_dir():
        return []
    collections = []
    for collection in sorted(project.iterdir()):
        if not (collection.is_dir() and _COLLECTION_RE.match(collection.name)):
            continue
        deployments = []
        for folder in sorted(collection.iterdir()):
            metadata = read_json(folder / DEPLOYMENT_METADATA_FILE) if folder.is_dir() and _DEPLOYMENT_RE.match(folder.name) else None
            if not isinstance(metadata, dict):
                continue
            log = read_json(folder / PREPROCESSING_LOG_FILE)
            upload = read_json(folder / UPLOAD_LOG_FILE)
            images = log["images"] if isinstance(log, dict) and isinstance(log.get("images"), list) else []
            deployments.append({
                "deployment_id": folder.name, "location_id": metadata.get("location_id"), "start_date": metadata.get("start_date"),
                "end_date": metadata.get("end_date"), "images": len(images),
                "bytes": sum(size_of(folder / e["name"]) for e in images if isinstance(e, dict) and e.get("name")),
                "preprocessed": isinstance(log, dict), "uploaded_at": upload.get("uploaded_at") if isinstance(upload, dict) else None,
            })
        collections.append({"name": collection.name, "path": str(collection), "deployments": deployments})
    return collections


class PlacesInUse(UploadPlaces):
    """Where the packages are made and how big a zip may be, as the settings say."""

    def __init__(self, packages_dir: Callable[[], Path], max_zip_mb: Callable[[], int]) -> None:
        self._packages_dir, self._max_zip_mb = packages_dir, max_zip_mb

    def packages_dir(self, project: str) -> Path:
        return self._packages_dir() / project

    def max_zip_bytes(self) -> int:
        return self._max_zip_mb() * 1024 * 1024
