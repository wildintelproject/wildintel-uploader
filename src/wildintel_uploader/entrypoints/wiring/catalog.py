"""The catalog of a collections folder — its use cases, its records for the backups, and where they are kept."""
from __future__ import annotations

from pathlib import Path

from dishka import Provider, Scope, alias, provide

from wildintel_uploader.modules.catalog.application.use_cases import CatalogUseCases
from wildintel_uploader.modules.catalog.domain.ports import (
    CatalogCheckpoints, CatalogEquipment, CatalogFieldwork, CatalogHistory, CatalogLocations, CatalogPeople, CatalogProjects, CatalogRepository, CatalogRoles, CatalogService, Clock,
)
from wildintel_uploader.modules.catalog.domain.records import CatalogRecordStore
from wildintel_uploader.modules.catalog.infrastructure.clock import SystemClock
from wildintel_uploader.modules.catalog.infrastructure.json_repository import StoreCatalogRepository
from wildintel_uploader.modules.catalog.infrastructure.legacy import FieldworkFromTheSettings, TrappersFromTheSettings
from wildintel_uploader.modules.catalog.infrastructure.project_folders import ResearchProjectFolders
from wildintel_uploader.modules.catalog.infrastructure.records import RecordStoreOf
from wildintel_uploader.modules.catalog.infrastructure.sql_repository import SqlCatalogRepository, sqlite_engine
from wildintel_uploader.modules.catalog.infrastructure.status_history import KeptStatusHistory
from wildintel_uploader.modules.catalog.infrastructure.visits import StoredVisits, VisitsAsKept
from wildintel_uploader.modules.settings.domain.ports import SettingsService
from wildintel_uploader.shared import storage
from wildintel_uploader.entrypoints import wiring as w   # the other factories, asked when called


def catalog_of(collections_dir: Path) -> CatalogService:
    """The catalog of a collections folder, with the settings of the app."""
    return build_catalog(collections_dir, w.build_settings())


def build_catalog(collections_dir: Path, settings: SettingsService, clock: Clock | None = None, repository: CatalogRepository | None = None) -> CatalogService:
    """The catalog of a collections folder — the one of the settings, or one a caller of before names —, taking what versions before left in the
    settings through their module. Its records are kept in `repository`, or — none given — where the settings say (see catalog_repository)."""
    store = storage.open_store(collections_dir)
    kept = repository or catalog_repository(collections_dir, settings)
    visits = VisitsAsKept(store, lambda: kept)   # the visits as they are kept, told with the catalog's own records: the catalog needs not the visits
    return CatalogUseCases(kept, folders=ResearchProjectFolders(lambda: collections_dir), legacy_trappers=TrappersFromTheSettings(settings), visits=StoredVisits(store, visits),
                           status_history=KeptStatusHistory(collections_dir, lambda: kept, lambda: visits), clock=clock or SystemClock(),
                           legacy_fieldwork=FieldworkFromTheSettings(settings))


def catalog_record_store(collections_dir: Path, settings: SettingsService | None = None) -> CatalogRecordStore:
    """The records of the catalog of a collections folder as they are kept, round its rules — for a backup only."""
    settings = settings or w.build_settings()
    kept = catalog_repository(collections_dir, settings)
    catalog = build_catalog(collections_dir, settings, repository=kept)
    return RecordStoreOf(lambda: kept, lambda: catalog)


def catalog_repository(collections_dir: Path, settings: SettingsService, kind: str | None = None, database: Path | None = None) -> CatalogRepository:
    """Where the catalog is kept, as the settings say (DATA.catalog_storage, DATA.catalog_database) — asked of their module —, or as `kind` and
    `database` say: "json", the files of the collections folder; "sqlite", a database (SqlCatalogRepository)."""
    places = settings.places()
    if (kind or places.catalog_storage) == "sqlite":
        return SqlCatalogRepository(sqlite_engine(database or places.catalog_database))
    return StoreCatalogRepository(storage.open_store(collections_dir))


class CatalogProvider(Provider):
    """The module of the catalog, kept in the collections folder the settings say."""

    @provide(scope=Scope.APP)
    def clock(self) -> Clock:
        return SystemClock()

    @provide(scope=Scope.REQUEST)
    def service(self, settings: SettingsService, clock: Clock) -> CatalogService:
        return build_catalog(w.catalog_collections_dir(), settings, clock)

    # each part of the contract, for whoever needs only that one: the same catalog of the request
    people = alias(source=CatalogService, provides=CatalogPeople)
    projects = alias(source=CatalogService, provides=CatalogProjects)
    locations = alias(source=CatalogService, provides=CatalogLocations)
    equipment = alias(source=CatalogService, provides=CatalogEquipment)
    roles = alias(source=CatalogService, provides=CatalogRoles)
    history = alias(source=CatalogService, provides=CatalogHistory)
    checkpoints = alias(source=CatalogService, provides=CatalogCheckpoints)
    fieldwork = alias(source=CatalogService, provides=CatalogFieldwork)
