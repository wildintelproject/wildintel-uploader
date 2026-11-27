"""The names of before of what the collections folder holds, for the code that still calls them — each now of its module (#248): the catalog as
records (tests.support.catalog_records, over modules.catalog), how a collection holds its deployments (modules.deployments.infrastructure.collections), the
visits kept (modules.visits.infrastructure.kept_visits.KeptVisits), the upload failures (modules.uploaders.infrastructure.failures) and why a status can't be
set by hand (modules.visits.domain.refusals). Nothing is decided here."""
from __future__ import annotations

from pathlib import Path

from tests.support.catalog_records import *  # noqa: F401,F403
from tests.support.catalog_records import _require_modifiable, _trapper_records  # noqa: F401 — the private names, which * leaves out
from wildintel_uploader.modules.deployments.infrastructure.collections import (  # noqa: F401
    COLLECTION_METADATA_FILE, DEPLOYMENT_METADATA_FILE, FIELDWORK_LOG_FIELDS, FIELDWORK_LOG_SUFFIX, IMAGES_FILE, TIMESTAMP_LOG_FIELDS, TIMESTAMP_LOG_SUFFIX,
    _read_json, check_collection, fieldwork_log_path, image_entry, imported_source_hashes, is_synced, list_deployments, project_dir, read_fieldwork_log,
    read_timestamp_log, timestamp_log_path, write_collection_metadata, write_deployment_metadata, write_images_file,
)
from wildintel_uploader.modules.visits.domain.refusals import camera_status_refusal as _camera_status_refusal  # noqa: F401
from wildintel_uploader.modules.visits.domain.refusals import card_status_refusal as _card_status_refusal  # noqa: F401
from wildintel_uploader.modules.visits.domain.refusals import site_status_refusal
from wildintel_uploader.modules.visits.domain.references import camera_model_of  # noqa: F401
from wildintel_uploader.modules.visits.domain.rules import closes_collection  # noqa: F401


def _kept_visits(root: Path):
    """The visits kept in this collections folder, as the app keeps them (modules.visits.infrastructure.kept_visits.KeptVisits)."""
    from wildintel_uploader.entrypoints.wiring import catalog_of
    from wildintel_uploader.modules.visits.infrastructure.kept_visits import KeptVisits
    return KeptVisits(root, lambda: catalog_of(root).records())


def _raw_visits(root: Path, research_project_id: str) -> list[dict]:
    return _kept_visits(root)._raw(research_project_id)


def _write_raw_visits(root: Path, research_project_id: str, visits: list[dict]) -> None:
    _kept_visits(root)._write_raw(research_project_id, visits)


def list_visits(root: Path, research_project_id: str, location_id: str | None = None, trappers=None) -> list[dict]:
    return _kept_visits(root).list(research_project_id, location_id, trappers)


def write_visit(root: Path, research_project_id: str, visit: dict) -> dict:
    return _kept_visits(root).add(research_project_id, visit)


def write_visits(root: Path, research_project_id: str, new: list[dict]) -> int:
    return _kept_visits(root).add_many(research_project_id, new)


def update_visit(root: Path, research_project_id: str, location_id: str, session: str, visit: dict) -> dict:
    return _kept_visits(root).update(research_project_id, location_id, session, visit)


def replace_visits(root: Path, research_project_id: str, visits: list[dict]) -> None:
    _kept_visits(root).replace_all(research_project_id, visits)


def write_states(root: Path, research_project_id: str, states: dict) -> int:
    return _kept_visits(root).write_states(research_project_id, states)


def closed_visits(root: Path, research_project_id: str) -> list[dict]:
    return _kept_visits(root).closed(research_project_id)


def link_visit(root: Path, research_project_id: str, location_id: str, date: str, time: str, deployment_id: str) -> dict:
    return _kept_visits(root).link(research_project_id, location_id, date, time, deployment_id)


def list_unknown(root: Path, research_project_id: str) -> list[dict]:
    return _kept_visits(root).unknown(research_project_id)


def write_unknown(root: Path, research_project_id: str, new: list[dict]) -> int:
    return _kept_visits(root).add_unknown(research_project_id, new)


def list_planned_revisions(root: Path, research_project_id: str) -> list[str]:
    return _kept_visits(root).planned_revisions(research_project_id)


def plan_revision(root: Path, research_project_id: str, session: str) -> str:
    return _kept_visits(root).plan_revision(research_project_id, session)


def _site_status_refusal(root: Path, research_project_id: str, locations: list[dict], location: dict, wanted: str) -> str | None:
    """Why the status of a site can't be set by hand — over the visits kept in this collections folder."""
    return site_status_refusal(list_visits(root, research_project_id), list_unknown(root, research_project_id), locations, location, wanted)


def _failures(root: Path):
    from wildintel_uploader.entrypoints.wiring import catalog_of
    from wildintel_uploader.modules.uploaders.infrastructure.failures import UploadFailures
    return UploadFailures(lambda: root, catalog_of)


def list_upload_failures(root: Path, research_project_id: str) -> list[dict]:
    return _failures(root).of(research_project_id)


def set_upload_failure(root: Path, research_project_id: str, deployment_id: str, destination: str, note: str | None) -> None:
    _failures(root).note(research_project_id, deployment_id, destination, note)
