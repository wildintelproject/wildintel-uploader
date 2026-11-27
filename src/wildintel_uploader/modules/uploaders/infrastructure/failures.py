"""The uploads that were tried and failed, kept in the folder of their research project (upload_failures.json): an upload that was done is not
there — it is told by the deployment's own folder —, and a success takes the failure away. Moved from the visits kept (#248)."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from wildintel_uploader.shared import storage


def _require_project(root: Path, research_project_id: str) -> None:
    """StorageError when the research project isn't kept — the catalog says it, through its contract."""
    from wildintel_uploader.entrypoints import wiring
    from wildintel_uploader.modules.catalog.domain.models import CatalogError, UnknownProject
    try:
        wiring.build_catalog(root, wiring.build_settings()).require_project(research_project_id)
    except (CatalogError, UnknownProject) as exc:
        raise storage.StorageError(getattr(exc, "message", str(exc))) from exc


def list_upload_failures(root: Path, research_project_id: str) -> list[dict]:
    """The uploads of the deployments of a research project that were tried and failed: {"deployment_id", "destination", "note", "at"}. An upload that was done is not here:
    it is told by the deployment's own folder — and a success takes the failure away."""
    return storage.open_store(root).read_records(research_project_id, "upload_failures")


def set_upload_failure(root: Path, research_project_id: str, deployment_id: str, destination: str, note: str | None) -> None:
    """Keeps that the upload of a deployment to a destination failed, with why — or, with no note (None), takes the failure away: it was tried again and worked.

    Raises:
        storage.StorageError: the research project isn't there."""
    _require_project(root, research_project_id)
    failures = [f for f in list_upload_failures(root, research_project_id) if not (f.get("deployment_id") == deployment_id and f.get("destination") == destination)]
    if note is not None:
        failures.append({"deployment_id": deployment_id, "destination": destination, "note": note.strip() or None, "at": datetime.now().astimezone().isoformat(timespec="seconds")})
    storage.open_store(root).write_records(research_project_id, "upload_failures", failures)
