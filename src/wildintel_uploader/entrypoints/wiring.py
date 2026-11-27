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

from functools import lru_cache
from pathlib import Path

from dishka import Container, Provider, Scope, make_container, provide

from wildintel_uploader.core import config, parallel
from wildintel_uploader.modules.backup.application.use_cases import BackupUseCases
from wildintel_uploader.modules.backup.domain.ports import BackupService
from wildintel_uploader.modules.backup.infrastructure.zip_files import ZipBackups
from wildintel_uploader.modules.catalog.application.use_cases import CatalogUseCases
from wildintel_uploader.modules.catalog.domain.ports import CatalogRepository, CatalogService, Clock
from wildintel_uploader.modules.catalog.infrastructure.json_repository import StoreCatalogRepository
from wildintel_uploader.modules.catalog.infrastructure.legacy import FieldworkFromTheSettings, SystemClock, TrappersFromTheSettings
from wildintel_uploader.modules.catalog.infrastructure.sql_repository import SqlCatalogRepository, sqlite_engine
from wildintel_uploader.modules.catalog.infrastructure.visits import StoredStatusHistory, StoredVisits
from wildintel_uploader.modules.deployments.application.use_cases import DeploymentsUseCases
from wildintel_uploader.modules.deployments.domain.ports import DeploymentsService
from wildintel_uploader.modules.deployments.infrastructure.legacy import (
    CollectionFolders as DeploymentFolders, DeploymentPhotos, KeptRepairs, KeptRevisions, KeptStatistics, LayoutOfTheCollections, MemoryCards, StoredSessions,
)
from wildintel_uploader.modules.fileinfo.application.use_cases import FileInfoUseCases
from wildintel_uploader.modules.fileinfo.domain.ports import FileInfoService
from wildintel_uploader.modules.fileinfo.infrastructure import exiftool as exiftool_adapter
from wildintel_uploader.modules.fileinfo.infrastructure.exiftool import ExifToolReader
from wildintel_uploader.modules.fileinfo.infrastructure.files import FileHasher, OsStamps
from wildintel_uploader.modules.fileinfo.infrastructure.memory import ProcessMemory
from wildintel_uploader.modules.fileinfo.infrastructure.pillow import PillowDecoder, PillowReader
from wildintel_uploader.modules.fileinfo.infrastructure.store import SqliteStore
from wildintel_uploader.modules.postvalidation.application.use_cases import PostvalidationUseCases
from wildintel_uploader.modules.postvalidation.domain.ports import PostvalidationService
from wildintel_uploader.modules.postvalidation.infrastructure import validators as deployment_validators
from wildintel_uploader.modules.postvalidation.infrastructure.legacy import CatalogCameras, LevelsInUse, RevisionsOfTheDeployments, SavedPostvalidationReports
from wildintel_uploader.modules.preprocessing.application.use_cases import PreprocessingUseCases
from wildintel_uploader.modules.preprocessing.domain.ports import PreprocessingService
from wildintel_uploader.modules.preprocessing.infrastructure import steps as preprocessing_steps
from wildintel_uploader.modules.preprocessing.infrastructure.folders import CollectionFolders, SavedReports
from wildintel_uploader.modules.prevalidation.application.use_cases import PrevalidationUseCases
from wildintel_uploader.modules.prevalidation.domain.ports import PrevalidationService
from wildintel_uploader.modules.prevalidation.infrastructure import validators as image_validators
from wildintel_uploader.modules.prevalidation.infrastructure.legacy import PreprocessedImages, SavedValidationReports, ValidationInUse
from wildintel_uploader.modules.reports.application.use_cases import ReportsUseCases
from wildintel_uploader.modules.reports.domain.ports import ReportsService
from wildintel_uploader.modules.reports.infrastructure.report_files import ReportFiles
from wildintel_uploader.modules.settings.application.use_cases import SettingsUseCases
from wildintel_uploader.modules.sources.application.use_cases import SourcesUseCases
from wildintel_uploader.modules.sources.domain.ports import SourcesService
from wildintel_uploader.modules.sources.infrastructure import sources as visit_sources
from wildintel_uploader.modules.sources.infrastructure.epicollect5 import PyEpicollect5
from wildintel_uploader.modules.sources.infrastructure.settings_in_use import SettingsOfTheSources
from wildintel_uploader.modules.sources.infrastructure.sources.epicollect_csv import form_columns, form_error
from wildintel_uploader.modules.timefix.application.use_cases import TimeFixUseCases
from wildintel_uploader.modules.timefix.domain.ports import TimeFixService
from wildintel_uploader.modules.timefix.infrastructure.legacy import ImagesWithExifTool, PeriodsOfTheVisits
from wildintel_uploader.modules.uploaders.application.use_cases import UploadersUseCases
from wildintel_uploader.modules.uploaders.domain.ports import UploadersService
from wildintel_uploader.modules.uploaders.infrastructure.trapper import CollectionsFolder, SavedUploadReports, TrapperClient
from wildintel_uploader.modules.uploaders.infrastructure.uploads import FolderUploads
from wildintel_uploader.modules.visits.application.use_cases import VisitsUseCases
from wildintel_uploader.modules.visits.domain.ports import VisitsService
from wildintel_uploader.modules.visits.infrastructure.legacy import (
    AuditClock, CatalogOfTheVisits, CsvVisitFile, DeploymentsOfTheVisits, FieldlogInUse, SavedVisitReports, StoredStateHistory, UploadsOfTheUploaders,
)
from wildintel_uploader.modules.visits.infrastructure.legacy import StoredVisits as KeptVisits
from wildintel_uploader.modules.settings.domain.ports import ActivityLog, Machine, RecordStorage, SettingsService, SettingsStore
from wildintel_uploader.modules.settings.infrastructure.system import AppActivityLog, AppRecordStorage, ThisMachine
from wildintel_uploader.shared import storage

# ── how each module is built ──


def build_reports() -> ReportsService:
    """The reports, as files in the reports folder — what the other modules keep the reports of what they did through."""
    return ReportsUseCases(ReportFiles())


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


@lru_cache(maxsize=1)
def file_info() -> FileInfoService:
    """What is known of the files of the images: one for the whole app, so that one reading of ExifTool runs at a time — the one that asks
    meanwhile waits for it, and finds what it read. ExifTool reads, Pillow only without it; remembered in memory and in the cache folder."""
    return FileInfoUseCases(reader=ExifToolReader(), fallback=PillowReader(), decoder=PillowDecoder(), hasher=FileHasher(), stamps=OsStamps(),
                            memory=ProcessMemory(), store=SqliteStore())


def build_prevalidation(info: FileInfoService | None = None) -> PrevalidationService:
    """The prevalidation: the validators of the images over what is known of the files, the images gone through in parallel."""
    return PrevalidationUseCases(info or file_info(), parallel.pmap, image_validators.VALIDATORS, imported=PreprocessedImages(build_deployments), settings=ValidationInUse(),
                                 reports=SavedValidationReports(build_reports()))


def build_postvalidation(info: FileInfoService | None = None) -> PostvalidationService:
    """The postvalidation: the validators of a deployment over its images and what is known of them."""
    return PostvalidationUseCases(info or file_info(), parallel.pmap, deployment_validators.VALIDATORS, cameras=CatalogCameras(lambda: build_catalog(catalog_collections_dir(), build_settings())), levels=LevelsInUse(),
                                  reports=SavedPostvalidationReports(build_reports()),
                                  revisions=RevisionsOfTheDeployments(build_deployments))


def build_preprocessing(info: FileInfoService | None = None) -> PreprocessingService:
    """The preprocessing: its steps over what is known of the files, in the collections folder as the rest of the app keeps it, with as many
    images at once as the settings say."""
    return PreprocessingUseCases(info or file_info(), CollectionFolders(lambda: build_deployments().layout()), SavedReports(build_reports()), image_steps=preprocessing_steps.IMAGE_STEPS,
                                 folder_steps=preprocessing_steps.FOLDER_STEPS, workers=config.workers, exiftool=lambda: exiftool_adapter.exiftool_path())


def build_sources(settings: SettingsService | None = None) -> SourcesService:
    """The sources of the visits: Epicollect5 through pyepicollect, the settings through their module."""
    return SourcesUseCases(PyEpicollect5(), SettingsOfTheSources(settings or build_settings()), visit_sources.SOURCES,
                           form_columns=form_columns, form_error=form_error)


def build_visits(collections_dir: Path | None = None, settings: SettingsService | None = None) -> VisitsService:
    """The visits of the research projects of a collections folder — the one of the settings by default —, over the code of before that keeps them."""
    root = collections_dir or catalog_collections_dir()
    settings = settings or build_settings()
    return VisitsUseCases(KeptVisits(root), CatalogOfTheVisits(root), deployments=DeploymentsOfTheVisits(root), file=CsvVisitFile(),
                          sources=build_sources(settings), uploads=UploadsOfTheUploaders(build_uploaders(root)), reports=SavedVisitReports(build_reports()), history=StoredStateHistory(),
                          settings=FieldlogInUse(), clock=AuditClock())


def build_deployments(settings: SettingsService | None = None) -> DeploymentsService:
    """The deployments: the cards, the folders, the revisions and the photos as the code of before keeps them, with the visits and the
    preprocessing through their contracts."""
    settings = settings or build_settings()
    return DeploymentsUseCases(MemoryCards(), DeploymentFolders(), KeptRevisions(), DeploymentPhotos(), visits=build_visits(settings=settings),
                               preprocessing=build_preprocessing(), repairs=KeptRepairs(), statistics=KeptStatistics(),
                               sessions=StoredSessions(), layout=LayoutOfTheCollections())


def build_timefix() -> TimeFixService:
    """The fixes of the dates of the images, over the code of before."""
    return TimeFixUseCases(PeriodsOfTheVisits(), ImagesWithExifTool())


def build_uploaders(collections_dir: Path | None = None) -> UploadersService:
    """The uploaders: TRAPPER through its client, the collections folder — the one of the settings by default — as the code of before keeps it."""
    return UploadersUseCases(TrapperClient(), CollectionsFolder(), SavedUploadReports(build_reports()),
                             FolderUploads(collections_dir or catalog_collections_dir()), deployments=build_deployments)


def build_backup() -> BackupService:
    """The backups, as zip files, over the code of before."""
    return BackupUseCases(ZipBackups())


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


class FileInfoProvider(Provider):
    """What is known of the files: the one of the app."""

    @provide(scope=Scope.APP)
    def service(self) -> FileInfoService:
        return file_info()


class ValidationProvider(Provider):
    """The prevalidation and the postvalidation."""

    @provide(scope=Scope.APP)
    def prevalidation(self, info: FileInfoService) -> PrevalidationService:
        return build_prevalidation(info)

    @provide(scope=Scope.APP)
    def postvalidation(self, info: FileInfoService) -> PostvalidationService:
        return build_postvalidation(info)


class PreprocessingProvider(Provider):
    """The preprocessing."""

    @provide(scope=Scope.APP)
    def service(self, info: FileInfoService) -> PreprocessingService:
        return build_preprocessing(info)


class SourcesProvider(Provider):
    """The sources of the visits."""

    @provide(scope=Scope.REQUEST)
    def service(self, settings: SettingsService) -> SourcesService:
        return build_sources(settings)


class VisitsProvider(Provider):
    """The visits, in the collections folder the settings say."""

    @provide(scope=Scope.REQUEST)
    def service(self, settings: SettingsService) -> VisitsService:
        return build_visits(catalog_collections_dir(), settings)


class DeploymentsProvider(Provider):
    """The deployments."""

    @provide(scope=Scope.REQUEST)
    def service(self, settings: SettingsService) -> DeploymentsService:
        return build_deployments(settings)


class TimeFixProvider(Provider):
    @provide(scope=Scope.APP)
    def service(self) -> TimeFixService:
        return build_timefix()


class UploadersProvider(Provider):
    @provide(scope=Scope.APP)
    def service(self) -> UploadersService:
        return build_uploaders()


class BackupProvider(Provider):
    @provide(scope=Scope.APP)
    def service(self) -> BackupService:
        return build_backup()


class ReportsProvider(Provider):
    @provide(scope=Scope.APP)
    def service(self) -> ReportsService:
        return build_reports()


def make_app_container() -> Container:
    """The container of the app: every module's provider."""
    return make_container(SettingsProvider(), CatalogProvider(), FileInfoProvider(), ValidationProvider(), PreprocessingProvider(), SourcesProvider(), VisitsProvider(), DeploymentsProvider(), TimeFixProvider(), UploadersProvider(), BackupProvider(), ReportsProvider())
