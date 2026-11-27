"""The uploads that were tried and failed, kept with the records of their research project (upload_failures): an upload that was done is not
there — it is told by the deployment's own folder —, and a success takes the failure away (domain.uploads)."""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from wildintel_uploader.modules.catalog.domain.models import CatalogError, UnknownProject
from wildintel_uploader.modules.catalog.domain.ports import CatalogService
from wildintel_uploader.modules.uploaders.domain import uploads as rules
from wildintel_uploader.shared import storage


class UploadFailures:
    """Those of the research projects of a collections folder (`root`, asked each time); the catalog of it says which research projects are kept."""

    def __init__(self, root: Callable[[], Path], catalog_of: Callable[[Path], CatalogService]) -> None:
        self._root, self._catalog_of = root, catalog_of

    def of(self, research_project_id: str) -> list[dict]:
        """{"deployment_id", "destination", "note", "at"} for each upload that was tried and failed."""
        return storage.open_store(self._root()).read_records(research_project_id, "upload_failures")

    def note(self, research_project_id: str, deployment_id: str, destination: str, note: str | None) -> None:
        """Keeps that the upload of a deployment to a destination failed, with why — or, with no note, takes the failure away.

        Raises:
            storage.StorageError: the research project isn't there."""
        root = self._root()
        try:
            self._catalog_of(root).require_project(research_project_id)
        except (CatalogError, UnknownProject) as exc:
            raise storage.StorageError(getattr(exc, "message", str(exc))) from exc
        at = datetime.now().astimezone().isoformat(timespec="seconds")
        storage.open_store(root).write_records(research_project_id, "upload_failures",
                                               rules.failures_after(self.of(research_project_id), deployment_id, destination, note, at))
