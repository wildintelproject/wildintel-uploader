"""Where the modules are put together (#248) — the composition root: the one place that chooses the implementation of each module's port in (its use
cases) and of its ports out (the adapters).

Each module is built by a function here (`build_…`): the Dishka providers below use them, and so do the entry points that build one on their own,
so that there is one way of putting a module together. Dishka works out the rest: to give a
CatalogService it gives the SettingsService the catalog asks for.

The entry points take the modules from the container made here — the web API through dishka's FastAPI integration (`web/main.py`), the command line
through `entrypoints.cli.injection` — and ask only for contracts: `FromDishka[SettingsService]`, `FromDishka[CatalogService]`.

What is made for a request or a command is made then (Scope.REQUEST), from the settings files config points at: so a test that points them elsewhere
is heeded. What lives as long as the app — with nothing to read anew — is Scope.APP."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from functools import lru_cache
from pathlib import Path

from dishka import Container, Provider, Scope, make_container, provide

from wildintel_uploader.entrypoints import config
from wildintel_uploader.shared import parallel
from wildintel_uploader.modules.backup.application.use_cases import BackupUseCases
from wildintel_uploader.modules.backup.domain.ports import BackupService
from wildintel_uploader.modules.backup.infrastructure.folders import CollectionsFolder as ProjectFoldersOnDisk
from wildintel_uploader.modules.backup.infrastructure.outside import RecordsOfTheProject, SettingsOfTheApp
from wildintel_uploader.modules.backup.infrastructure.zip_files import ZipBackups
from wildintel_uploader.shared.version import current_version
from wildintel_uploader.modules.catalog.application.use_cases import CatalogUseCases
from wildintel_uploader.modules.catalog.domain.ports import CatalogRepository, CatalogService, Clock
from wildintel_uploader.modules.catalog.infrastructure.json_repository import StoreCatalogRepository
from wildintel_uploader.modules.catalog.infrastructure.records import RecordsOf
from wildintel_uploader.modules.catalog.infrastructure.clock import SystemClock
from wildintel_uploader.modules.catalog.infrastructure.legacy import FieldworkFromTheSettings, TrappersFromTheSettings
from wildintel_uploader.modules.catalog.infrastructure.sql_repository import SqlCatalogRepository, sqlite_engine
from wildintel_uploader.modules.catalog.infrastructure.status_history import KeptStatusHistory
from wildintel_uploader.modules.catalog.infrastructure.visits import StoredVisits
from wildintel_uploader.modules.deployments.application.cards import CardCopying
from wildintel_uploader.modules.deployments.application.imports import Importing
from wildintel_uploader.modules.deployments.infrastructure.import_folder import ImportFolderOnDisk
from wildintel_uploader.modules.deployments.application.repair import Repairing
from wildintel_uploader.modules.deployments.infrastructure.memory_cards import CardOnDisk, CopiesInTemp
from wildintel_uploader.modules.deployments.application.seal import Sealing
from wildintel_uploader.modules.deployments.infrastructure.repair_folder import RepairFolderOnDisk
from wildintel_uploader.modules.deployments.application.statistics import RevisionStatistics
from wildintel_uploader.modules.deployments.infrastructure.sealed_folder import ChecksInUse, DeploymentSealFolder
from wildintel_uploader.modules.deployments.application.use_cases import DeploymentsUseCases
from wildintel_uploader.modules.deployments.infrastructure.revision_folders import RevisionFoldersOnDisk, StatisticsInUse
from wildintel_uploader.modules.deployments.domain.ports import DeploymentsService
from wildintel_uploader.modules.deployments.application.photos import DeploymentPhotos
from wildintel_uploader.modules.deployments.application.sessions import WizardSessions
from wildintel_uploader.modules.deployments.infrastructure.collection_layout import LayoutOfTheCollections
from wildintel_uploader.modules.deployments.infrastructure.collections_folder import CollectionFolders as DeploymentFolders
from wildintel_uploader.modules.deployments.infrastructure.photo_folder import PhotosOnDisk
from wildintel_uploader.modules.deployments.infrastructure.session_folder import SessionsOnDisk
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
from wildintel_uploader.modules.postvalidation.infrastructure.adapters import CatalogCameras, LevelsInUse, RevisionsOfTheDeployments, SavedPostvalidationReports
from wildintel_uploader.modules.preprocessing.application.use_cases import PreprocessingUseCases
from wildintel_uploader.modules.preprocessing.domain.ports import PreprocessingService
from wildintel_uploader.modules.preprocessing.infrastructure import steps as preprocessing_steps
from wildintel_uploader.modules.preprocessing.infrastructure.folders import CollectionFolders, SavedReports
from wildintel_uploader.modules.prevalidation.application.use_cases import PrevalidationUseCases
from wildintel_uploader.modules.prevalidation.domain.ports import PrevalidationService
from wildintel_uploader.modules.prevalidation.infrastructure import validators as image_validators
from wildintel_uploader.modules.prevalidation.infrastructure.adapters import PreprocessedImages, SavedValidationReports, ValidationInUse
from wildintel_uploader.modules.reports.application.use_cases import ReportsUseCases
from wildintel_uploader.modules.reports.domain.ports import ReportsService
from wildintel_uploader.modules.reports.infrastructure.report_files import ImagesOnDisk, ReportFiles
from wildintel_uploader.modules.settings.application.use_cases import SettingsUseCases
from wildintel_uploader.modules.sources.application.use_cases import SourcesUseCases
from wildintel_uploader.modules.sources.domain.ports import SourcesService
from wildintel_uploader.modules.sources.infrastructure import sources as visit_sources
from wildintel_uploader.modules.sources.infrastructure.epicollect5 import PyEpicollect5
from wildintel_uploader.modules.sources.infrastructure.settings_in_use import SettingsOfTheSources
from wildintel_uploader.modules.sources.infrastructure.sources.epicollect_csv import form_columns, form_error
from wildintel_uploader.modules.timefix.application.use_cases import TimeFixUseCases
from wildintel_uploader.modules.timefix.domain.ports import TimeFixService
from wildintel_uploader.modules.timefix.infrastructure.corrections import CorrectionsFile
from wildintel_uploader.modules.timefix.infrastructure.images import ExifToolShifter, FolderOfImages
from wildintel_uploader.modules.timefix.infrastructure.outside import ToleranceInUse, VisitsThroughTheirContract
from wildintel_uploader.modules.uploaders.application.use_cases import UploadersUseCases
from wildintel_uploader.modules.uploaders.domain.ports import UploadersService
from wildintel_uploader.modules.uploaders.application.sync import TrapperSync
from wildintel_uploader.modules.uploaders.application.upload import TrapperUploads
from wildintel_uploader.modules.uploaders.infrastructure.synced_folder import SyncedCollections
from wildintel_uploader.modules.uploaders.infrastructure.failures import UploadFailures
from wildintel_uploader.modules.uploaders.infrastructure.packages import DeploymentFolder, PackagesOnDisk
from wildintel_uploader.modules.uploaders.infrastructure.trapper import CollectionsFolder, PlacesInUse, SavedUploadReports, TrapperClient
from wildintel_uploader.modules.uploaders.infrastructure.trapper_site import TrapperSdk
from wildintel_uploader.modules.uploaders.infrastructure.uploads import FolderUploads
from wildintel_uploader.modules.visits.application.use_cases import VisitsUseCases
from wildintel_uploader.modules.visits.domain.ports import VisitsService
from wildintel_uploader.modules.visits.infrastructure.adapters import (
    AuditClock, CatalogOfTheVisits, CollectionFolders as VisitCollectionFolders, FieldlogInUse, SavedVisitReports, StoredStateHistory, UploadsOfTheUploaders,
)
from wildintel_uploader.modules.visits.infrastructure.adapters import StoredVisits as VisitsKept
from wildintel_uploader.modules.visits.infrastructure.kept_visits import KeptVisits
from wildintel_uploader.modules.visits.infrastructure.csv_file import CsvVisitFile
from wildintel_uploader.modules.settings.domain.ports import ActivityLog, Machine, RecordStorage, SettingsService, SettingsStore
from wildintel_uploader.modules.settings.infrastructure.system import AppActivityLog, AppRecordStorage, ThisMachine
from wildintel_uploader.shared import storage

# ── how each module is built ──

# how many images are worked on at once: the setting GENERAL.workers, asked each time
parallel.use_workers(lambda: config.workers())


def catalog_of(collections_dir: Path) -> CatalogService:
    """The catalog of a collections folder, with the settings of the app."""
    return build_catalog(collections_dir, build_settings())


def build_reports(reports_dir: Path | None = None) -> ReportsService:
    """The reports, as files in the reports folder — the settings' by default —, the failed images dated as modules.fileinfo reads them: what
    the other modules keep the reports of what they did through."""
    return ReportsUseCases(ReportFiles(lambda: reports_dir or config.reports_dir()), ImagesOnDisk(), file_info())


def section(name: str) -> Callable[[], Any]:
    """A section of the settings as settings.toml keeps them (VALIDATION, TRAPPER…) — what an adapter is given of them, asked each time."""
    return lambda: getattr(config.load_settings(), name)


def keep_trapper_account(credentials) -> None:
    """The account of TRAPPER kept in the settings: its address, its user and its password."""
    settings = config.load_settings()
    settings.TRAPPER.base_url, settings.TRAPPER.user_name, settings.TRAPPER.user_password = credentials
    config.save_settings(settings)


def app_log() -> AppActivityLog:
    """The log of the app, in the log folder and at the level the settings say — what the entry points set up when they start."""
    return AppActivityLog(lambda: config.get_logs_dir(), lambda: config.legacy_logs_dir(), lambda: config.load_settings().GENERAL.log_level)


def error_words(exc: Exception) -> str:
    """What an error says to a person, as the web API tells it: TRAPPER's, the network's, or the words of what the modules refuse."""
    from wildintel_uploader.modules.uploaders.infrastructure.trapper import as_uploader_error
    return as_uploader_error(exc).message


def build_settings(store: SettingsStore | None = None, *, activity_log: ActivityLog | None = None, machine: Machine | None = None,
                   record_storage: RecordStorage | None = None) -> SettingsService:
    """The settings: their use cases over the TOML files of the user's config folder, the log of the app, this computer and the backends of the
    records."""
    return SettingsUseCases(store or config.settings_store(), config.default_data_dir(), activity_log=activity_log or app_log(),
                            machine=machine or ThisMachine(), record_storage=record_storage or AppRecordStorage())


def build_catalog(collections_dir: Path, settings: SettingsService, clock: Clock | None = None, repository: CatalogRepository | None = None) -> CatalogService:
    """The catalog of a collections folder — the one of the settings, or one a caller of before names —, taking what versions before left in the
    settings through their module. Its records are kept in `repository`, or — none given — where the settings say (see catalog_repository)."""
    store = storage.open_store(collections_dir)
    kept = repository or catalog_repository(collections_dir, settings)
    catalog: list[CatalogService] = []     # the records are the catalog's own, as records: they are given it once it is made
    made = CatalogUseCases(kept, legacy_trappers=TrappersFromTheSettings(settings), visits=StoredVisits(store, lambda: build_visits(collections_dir)),
                           status_history=KeptStatusHistory(collections_dir, lambda: kept, lambda: build_visits(collections_dir)), clock=clock or SystemClock(),
                           legacy_fieldwork=FieldworkFromTheSettings(settings), records=RecordsOf(lambda: catalog[0], lambda: kept))
    catalog.append(made)
    return made


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
    return PrevalidationUseCases(info or file_info(), parallel.pmap, image_validators.VALIDATORS, imported=PreprocessedImages(build_deployments), settings=ValidationInUse(section("VALIDATION")),
                                 reports=SavedValidationReports(build_reports()))


def build_postvalidation(info: FileInfoService | None = None) -> PostvalidationService:
    """The postvalidation: the validators of a deployment over its images and what is known of them."""
    return PostvalidationUseCases(info or file_info(), parallel.pmap, deployment_validators.VALIDATORS, cameras=CatalogCameras(lambda: build_catalog(catalog_collections_dir(), build_settings())), levels=LevelsInUse(section("VALIDATION")),
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
    """The visits of the research projects of a collections folder — the one of the settings by default —, kept with the records of their research projects."""
    root = collections_dir or catalog_collections_dir()
    settings = settings or build_settings()
    records = lambda: build_catalog(root, settings).records()   # noqa: E731
    return VisitsUseCases(VisitsKept(KeptVisits(root, records)), CatalogOfTheVisits(records),
                          deployments=VisitCollectionFolders(root, lambda: build_deployments().layout()), file=CsvVisitFile(),
                          sources=build_sources(settings), uploads=UploadsOfTheUploaders(build_uploaders(root)), reports=SavedVisitReports(build_reports()), history=StoredStateHistory(),
                          settings=FieldlogInUse(section("FIELDLOG")), clock=AuditClock())


def build_deployments(settings: SettingsService | None = None) -> DeploymentsService:
    """The deployments: the memory cards, the collections folder, the import, the revisions, the photos and the wizard's sessions over their
    adapters, with the visits and the preprocessing through their contracts."""
    settings = settings or build_settings()
    return DeploymentsUseCases(CardCopying(CardOnDisk(), CopiesInTemp()), DeploymentFolders(lambda: config.collections_dir(), catalog_of, sealing), revision_statistics(),
                               DeploymentPhotos(PhotosOnDisk(lambda: config.collections_dir())), visits=build_visits(settings=settings),
                               preprocessing=build_preprocessing(), repairs=repairing(), statistics=revision_statistics(),
                               sessions=WizardSessions(SessionsOnDisk(lambda: config.get_sessions_dir(), lambda: config.legacy_sessions_dir())), layout=LayoutOfTheCollections(importing), imports=importing())


def importing() -> Importing:
    """Bringing a folder of images into a collection of the collections folder of the settings: the images through modules.fileinfo, then sealed."""
    return Importing(ImportFolderOnDisk(lambda: config.collections_dir()), file_info, sealing,
                     exif_fields=lambda: config.load_settings().VALIDATION.exif_fields)


def sealing() -> Sealing:
    """The seal of the deployments: the checks the settings turn on, the prevalidation's and the postvalidation's through their contracts."""
    return Sealing(DeploymentSealFolder(), ChecksInUse(section("VALIDATION"), section("POSTVALIDATION")), prevalidation=build_prevalidation, postvalidation=build_postvalidation,
                   catalog_of=catalog_of, revisions_of=lambda root: RevisionStatistics(RevisionFoldersOnDisk(lambda: root, file_info), StatisticsInUse(section("POSTVALIDATION"))))


def repairing() -> Repairing:
    """Repairing the deployments kept in the collections folder of the settings: sealed again, reported, the catalog through its contract."""
    return Repairing(RepairFolderOnDisk(lambda: config.collections_dir(), file_info), sealing, build_reports, lambda: catalog_of(config.collections_dir()),
                     lambda: config.load_settings().PREPROCESSING.model_dump())


def revision_statistics() -> RevisionStatistics:
    """The statistics of the deployments kept in the collections folder of the settings, as POSTVALIDATION says."""
    return RevisionStatistics(RevisionFoldersOnDisk(lambda: config.collections_dir(), file_info), StatisticsInUse(section("POSTVALIDATION")))


def build_timefix() -> TimeFixService:
    """The fixes of the dates of the images: the visits of the collections folder of the settings, the images on disk and their dates as
    modules.fileinfo reads them, ExifTool to shift them, the fixes written down beside them."""
    files = file_info()
    return TimeFixUseCases(VisitsThroughTheirContract(lambda: build_visits()), FolderOfImages(), files, ExifToolShifter(files.exiftool_path),
                           CorrectionsFile(), ToleranceInUse(section("POSTVALIDATION")))


def build_uploaders(collections_dir: Path | None = None) -> UploadersService:
    """The uploaders: TRAPPER through its client, the collections folder — the one of the settings by default — with the uploads kept in it."""
    root = collections_dir or catalog_collections_dir()
    failures = UploadFailures(lambda: root, catalog_of)
    return UploadersUseCases(TrapperClient(section("TRAPPER"), keep_trapper_account, TrapperSdk()), CollectionsFolder(lambda: config.collections_dir(), catalog_of, UploadFailures(lambda: config.collections_dir(), catalog_of)),
                             SavedUploadReports(build_reports()), FolderUploads(root, section("TRAPPER"), section("AGOUTI"), lambda: build_deployments().layout(), failures),
                             deployments=build_deployments,
                             sending=trapper_uploads(), places=PlacesInUse(lambda: config.packages_dir(), lambda: config.max_zip_mb()),
                             syncing=TrapperSync(TrapperSdk(), lambda: catalog_of(config.collections_dir()).records(),
                                                 SyncedCollections(lambda: config.collections_dir(), lambda: build_deployments().layout())))


def trapper_uploads() -> TrapperUploads:
    """Uploading to TRAPPER: its API through its SDK, the deployments kept and the packages on disk."""
    return TrapperUploads(TrapperSdk(), DeploymentFolder(), PackagesOnDisk())


def build_backup(collections_dir: Path | None = None, version: Callable[[], str] = current_version) -> BackupService:
    """The backups, as zip files, of the collections folder — the settings' by default —: the catalog and the visits through their contracts."""
    def root() -> Path:
        return collections_dir or config.collections_dir()
    return BackupUseCases(RecordsOfTheProject(root, lambda r: catalog_of(r).records(), lambda r: build_visits(r)), ProjectFoldersOnDisk(root), ZipBackups(),
                          SettingsOfTheApp(config), version)


# ── the providers of the container ──


class SettingsProvider(Provider):
    """The module of the settings."""

    @provide(scope=Scope.REQUEST)
    def store(self) -> SettingsStore:
        return config.settings_store()

    @provide(scope=Scope.APP)
    def activity_log(self) -> ActivityLog:
        return app_log()

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
