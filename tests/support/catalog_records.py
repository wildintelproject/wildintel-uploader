"""The catalog as records, as the tests of before call it — by the collections folder — over the class the app uses
(modules.catalog.infrastructure.records.RecordsOf, put together by entrypoints.wiring)."""
from pathlib import Path

from wildintel_uploader.modules.catalog.infrastructure.records import (  # noqa: F401
    CAMERAS_FILE, LOCATIONS_FILE, RESEARCH_PROJECT_METADATA_FILE, SD_CARDS_FILE, UNKNOWN_FILE, UPLOAD_FAILURES_FILE, VISITS_FILE, LocalFolderError,
)


def _records(root: Path):
    from wildintel_uploader.entrypoints.wiring import catalog_of
    return catalog_of(root).records()


def list_research_projects(root: Path, include_deleted: bool = False) -> list[dict]:
    return _records(root).research_projects(include_deleted)


def has_research_project(root: Path, research_project_id: str) -> bool:
    return _records(root).has_project(research_project_id)


def write_research_project(root: Path, project: dict) -> dict:
    return _records(root).add_project(project)


def update_research_project(root: Path, research_project_id: str, changes: dict) -> dict:
    return _records(root).update_project(research_project_id, changes)


def delete_research_project(root: Path, research_project_id: str) -> dict:
    return _records(root).delete_project(research_project_id)


def _require_modifiable(root: Path, research_project_id: str) -> None:
    _records(root).require_modifiable(research_project_id)


def list_locations(root: Path, research_project_id: str, include_deleted: bool = False) -> list[dict]:
    return _records(root).locations(research_project_id, include_deleted)


def write_location(root: Path, research_project_id: str, location: dict, by_hand: bool = False) -> dict:
    return _records(root).add_location(research_project_id, location, by_hand)


def update_location(root: Path, research_project_id: str, location_id: str, changes: dict, by_visit: bool = False) -> dict:
    return _records(root).change_location(research_project_id, location_id, changes, by_visit)


def delete_location(root: Path, research_project_id: str, location_id: str) -> dict:
    return _records(root).delete_location(research_project_id, location_id)


def list_field_items(root: Path, research_project_id: str, kind: str, include_deleted: bool = False) -> list[dict]:
    return _records(root).equipment(research_project_id, kind, include_deleted)


def camera_record(root: Path, research_project_id: str | None, key: str | None) -> dict | None:
    return _records(root).camera(research_project_id, key)


def set_camera_identity(root: Path, research_project_id: str, label: str, make: str | None, model: str | None) -> dict:
    return _records(root).set_camera_identity(research_project_id, label, make, model)


def write_field_items(root: Path, research_project_id: str, kind: str, items: list[dict], by_hand: bool = False) -> None:
    _records(root).keep_equipment(research_project_id, kind, items, by_hand)


def project_record(root: Path, research_project_id: str) -> dict | None:
    return _records(root).project_record(research_project_id)


def put_project_record(root: Path, record: dict) -> None:
    _records(root).put_project_record(record)


def equipment_records(root: Path, research_project_id: str, kind: str) -> list[dict]:
    return _records(root).equipment_records(research_project_id, kind)


def put_equipment_records(root: Path, research_project_id: str, kind: str, records: list[dict]) -> None:
    _records(root).put_equipment_records(research_project_id, kind, records)


def location_records(root: Path, research_project_id: str) -> list[dict]:
    return _records(root).location_records(research_project_id)


def put_location_records(root: Path, research_project_id: str, records: list[dict]) -> None:
    _records(root).put_location_records(research_project_id, records)


def list_trappers(root: Path, include_deleted: bool = False) -> list[dict]:
    return _records(root).trappers(include_deleted)


def write_trappers(root: Path, trappers: list[dict]) -> None:
    _records(root).keep_trappers(trappers)


def _trapper_records(root: Path, trappers=None) -> list[dict]:
    return _records(root).trapper_records() if trappers is None else [t if isinstance(t, dict) else t.model_dump(mode="json") for t in trappers]


def list_roles(root: Path, research_project_id: str, include_deleted: bool = False, trappers=None) -> list[dict]:
    return _records(root).roles(research_project_id, include_deleted)


def write_roles(root: Path, research_project_id: str, roles: list[dict], trappers=None) -> None:
    _records(root).keep_roles(research_project_id, roles)


def list_all_field_items(root: Path, kind: str) -> list[dict]:
    return _records(root).all_equipment(kind)


def list_all_roles(root: Path, trappers=None) -> list[dict]:
    return [role for project in list_research_projects(root) for role in list_roles(root, project["acronym"])]


def require_research_project(root: Path, research_project_id: str) -> None:
    _records(root).require_project(research_project_id)


def require_active_research_project(root: Path, research_project_id: str) -> None:
    _records(root).require_project(research_project_id, active=True)


def location_time(root: Path, research_project_id: str, location_id: str | None) -> dict:
    return _records(root).location_time(research_project_id, location_id)


def location_time_in(project_folder: Path, location_id: str | None) -> dict:
    from wildintel_uploader.shared.storage import valid_project_id
    try:
        valid_project_id(project_folder.name)
    except LocalFolderError:
        return {}
    return location_time(project_folder.parent, project_folder.name, location_id)
