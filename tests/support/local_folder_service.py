"""The names of before of what the collections folder holds, for the code that still calls them — each now of its module (#248): the catalog as
records (tests.support.catalog_records, over modules.catalog), how a collection holds its deployments (modules.deployments.infrastructure.collections), the
visits kept (modules.visits.infrastructure.kept_visits), the upload failures (modules.uploaders.infrastructure.failures) and why a status can't be
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
from wildintel_uploader.modules.visits.infrastructure.kept_visits import (  # noqa: F401
    _CALLED, _POINTS_TO, _kept, _linked, _raw_visits, _refs, _Refs, _site, _told, _unlinked, _write_raw_visits, _write_unknown, camera_model_of,
    closed_visits, closes_collection, link_visit, list_planned_revisions, list_unknown, list_visits, plan_revision, replace_visits, update_visit,
    write_states, write_unknown, write_visit, write_visits,
)


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
