"""What the backups take from other modules: the records of a research project — the catalog and the visits through their contracts, the history
of the states as the project store keeps it —, and the settings of the app as settings.toml keeps them."""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from wildintel_uploader.modules.backup.domain.ports import AppSettings, BackupError
from wildintel_uploader.modules.catalog.domain.records import CatalogRecords, CatalogRecordStore
from wildintel_uploader.modules.settings.domain.ports import StoredSettings
from wildintel_uploader.modules.visits.domain.ports import VisitsService
from wildintel_uploader.shared import storage


class RecordsOfTheProject:
    """The records of the research projects of a collections folder (`root`, asked each time)."""

    def __init__(self, root: Callable[[], Path], catalog: Callable[[Path], CatalogRecords], store: Callable[[Path], CatalogRecordStore],
                 visits: Callable[[Path], VisitsService]) -> None:
        """`catalog` gives the catalog of a collections folder as records, through its rules; `store` its records as they are kept, which a
        backup copies and restores as they are."""
        self._root, self._catalog, self._store, self._visits = root, catalog, store, visits

    def _records(self) -> CatalogRecords:
        return self._catalog(self._root())

    def _kept(self) -> CatalogRecordStore:
        return self._store(self._root())

    def require_project(self, project: str) -> None:
        try:
            self._records().require_project(project)
        except storage.StorageError as exc:
            raise BackupError(str(exc)) from exc

    def has_project(self, project: str) -> bool:
        return self._records().has_project(project)

    def project_record(self, project: str) -> dict | None:
        return self._kept().project_record(project)

    def put_project_record(self, record: dict) -> None:
        self._kept().put_project_record(record)

    def locations(self, project: str) -> list[dict]:
        return self._records().locations(project)

    def location_records(self, project: str) -> list[dict]:
        return self._kept().location_records(project)

    def put_location_records(self, project: str, records: list[dict]) -> None:
        self._kept().put_location_records(project, records)

    def equipment(self, project: str, kind: str) -> list[dict]:
        return self._records().equipment(project, kind)

    def equipment_records(self, project: str, kind: str) -> list[dict]:
        return self._kept().equipment_records(project, kind)

    def put_equipment_records(self, project: str, kind: str, records: list[dict]) -> None:
        self._kept().put_equipment_records(project, kind, records)

    def roles(self, project: str, include_deleted: bool = False) -> list[dict]:
        return self._records().roles(project, include_deleted=include_deleted)

    def keep_roles(self, project: str, roles: list[dict]) -> None:
        self._records().keep_roles(project, roles)

    def trappers(self) -> list[dict]:
        return self._records().trappers()

    def keep_trappers(self, trappers: list[dict]) -> None:
        self._records().keep_trappers(trappers)

    def status_history(self, project: str) -> list[dict]:
        return storage.open_store(self._root()).read_records(project, "status_history")

    def keep_status_history(self, project: str, lines: list[dict]) -> None:
        storage.open_store(self._root()).write_records(project, "status_history", lines)

    def visits(self, project: str) -> list[dict]:
        return self._visits(self._root()).visits(project)

    def kept_visits(self, project: str) -> int:
        return self._visits(self._root()).kept_count(project)

    def replace_visits(self, project: str, visits: list[dict]) -> None:
        self._visits(self._root()).replace_all(project, visits)


class SettingsOfTheApp(AppSettings):
    def __init__(self, settings: StoredSettings) -> None:
        self._settings = settings

    def as_data(self) -> dict:
        return self._settings.load_settings().model_dump(mode="json")

    def secrets(self) -> list[tuple[str, str]]:
        return list(self._settings.secret_fields())

    def save(self, data: dict) -> None:
        try:
            self._settings.save_settings(self._settings.Settings.model_validate(data, context={"migrate": True}))
        except Exception as exc:  # a setting the backup holds that this version does not accept
            raise BackupError(f"The settings of the backup cannot be restored: {exc}") from exc
