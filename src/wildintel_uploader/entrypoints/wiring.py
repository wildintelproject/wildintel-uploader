"""Where the modules are put together (#248) — the composition root: the one place that chooses the implementation of each module's port in (its use
cases) and of its ports out (the adapters).

Each module is built by a function here (`build_…`): the Dishka providers below use them, and so does the code from before that still calls the old
services (core/services/local_folder_service.py), so that there is one way of putting a module together. Dishka works out the rest: to give a
CatalogService it gives the SettingsService the catalog asks for.

The entry points take the modules from the container made here — the web API through dishka's FastAPI integration (`web/main.py`), the command line
through `entrypoints.cli.injection` — and ask only for contracts: `FromDishka[SettingsService]`, `FromDishka[CatalogService]`.

What is made for a request or a command is made then (Scope.REQUEST), from the settings files config points at: so a test that points them elsewhere
is heeded. What lives as long as the app — with nothing to read anew — is Scope.APP."""
from __future__ import annotations

from pathlib import Path

from dishka import Container, Provider, Scope, make_container, provide

from wildintel_uploader.core import config
from wildintel_uploader.modules.catalog.application.use_cases import CatalogUseCases
from wildintel_uploader.modules.catalog.domain.ports import CatalogRepository, CatalogService, Clock
from wildintel_uploader.modules.catalog.infrastructure.json_repository import StoreCatalogRepository
from wildintel_uploader.modules.catalog.infrastructure.legacy import FieldworkFromTheSettings, SystemClock, TrappersFromTheSettings
from wildintel_uploader.modules.catalog.infrastructure.sql_repository import SqlCatalogRepository, sqlite_engine
from wildintel_uploader.modules.catalog.infrastructure.visits import StoredStatusHistory, StoredVisits
from wildintel_uploader.modules.settings.application.use_cases import SettingsUseCases
from wildintel_uploader.modules.settings.domain.ports import ActivityLog, Machine, RecordStorage, SettingsService, SettingsStore
from wildintel_uploader.modules.settings.infrastructure.system import AppActivityLog, AppRecordStorage, ThisMachine
from wildintel_uploader.shared import storage

# ── how each module is built ──


def build_settings(store: SettingsStore | None = None, *, activity_log: ActivityLog | None = None, machine: Machine | None = None,
                   record_storage: RecordStorage | None = None) -> SettingsService:
    """The settings: their use cases over the TOML files of the user's config folder, the log of the app, this computer and the backends of the
    records."""
    return SettingsUseCases(store or config.settings_store(), config.default_data_dir(), activity_log=activity_log or AppActivityLog(),
                            machine=machine or ThisMachine(), record_storage=record_storage or AppRecordStorage())


def build_catalog(collections_dir: Path, settings: SettingsService, clock: Clock | None = None, repository: CatalogRepository | None = None) -> CatalogService:
    """The catalog of a collections folder — the one of the settings, or one a caller of before names —, taking what versions before left in the
    settings through their module. Its records are kept in `repository`, or — none given — where the settings say (see catalog_repository)."""
    store = storage.open_store(collections_dir)
    return CatalogUseCases(repository or catalog_repository(collections_dir, settings), legacy_trappers=TrappersFromTheSettings(settings),
                           visits=StoredVisits(store, collections_dir), status_history=StoredStatusHistory(collections_dir), clock=clock or SystemClock(),
                           legacy_fieldwork=FieldworkFromTheSettings(settings))


def catalog_repository(collections_dir: Path, settings: SettingsService, kind: str | None = None, database: Path | None = None) -> CatalogRepository:
    """Where the catalog is kept, as the settings say (DATA.catalog_storage, DATA.catalog_database) — asked of their module —, or as `kind` and
    `database` say: "json", the files of the collections folder; "sqlite", a database (SqlCatalogRepository)."""
    places = settings.places()
    if (kind or places.catalog_storage) == "sqlite":
        return SqlCatalogRepository(sqlite_engine(database or places.catalog_database), collections_dir)
    return StoreCatalogRepository(storage.open_store(collections_dir), collections_dir)


# ── the providers of the container ──


class SettingsProvider(Provider):
    """The module of the settings."""

    @provide(scope=Scope.REQUEST)
    def store(self) -> SettingsStore:
        return config.settings_store()

    @provide(scope=Scope.APP)
    def activity_log(self) -> ActivityLog:
        return AppActivityLog()

    @provide(scope=Scope.APP)
    def machine(self) -> Machine:
        return ThisMachine()

    @provide(scope=Scope.APP)
    def record_storage(self) -> RecordStorage:
        return AppRecordStorage()

    @provide(scope=Scope.REQUEST)
    def service(self, store: SettingsStore, activity_log: ActivityLog, machine: Machine, record_storage: RecordStorage) -> SettingsService:
        return build_settings(store, activity_log=activity_log, machine=machine, record_storage=record_storage)


def catalog_collections_dir() -> Path:
    """The collections folder the catalog of a request or a command is kept in: the one the settings say."""
    return config.collections_dir()


class CatalogProvider(Provider):
    """The module of the catalog, kept in the collections folder the settings say."""

    @provide(scope=Scope.APP)
    def clock(self) -> Clock:
        return SystemClock()

    @provide(scope=Scope.REQUEST)
    def service(self, settings: SettingsService, clock: Clock) -> CatalogService:
        return build_catalog(catalog_collections_dir(), settings, clock)


def make_app_container() -> Container:
    """The container of the app: every module's provider."""
    return make_container(SettingsProvider(), CatalogProvider())
