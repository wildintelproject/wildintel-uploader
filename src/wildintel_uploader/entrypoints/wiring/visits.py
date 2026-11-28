"""The visits, their sources (Epicollect5, files) and the fixes of the dates of the images."""
from __future__ import annotations

from pathlib import Path

from dishka import Provider, Scope, alias, provide

from wildintel_uploader.modules.settings.domain.ports import SettingsService
from wildintel_uploader.modules.sources.application.use_cases import SourcesUseCases
from wildintel_uploader.modules.sources.domain.ports import SourcesDeployments, SourcesProject, SourcesService, SourcesVisits
from wildintel_uploader.modules.sources.infrastructure import sources as visit_sources
from wildintel_uploader.modules.sources.infrastructure.epicollect5 import PyEpicollect5
from wildintel_uploader.modules.sources.infrastructure.settings_in_use import SettingsOfTheSources
from wildintel_uploader.modules.sources.infrastructure.sources.epicollect_csv import form_columns, form_error
from wildintel_uploader.modules.timefix.application.use_cases import TimeFixUseCases
from wildintel_uploader.modules.timefix.domain.ports import TimeFixService
from wildintel_uploader.modules.timefix.infrastructure.corrections import CorrectionsFile
from wildintel_uploader.modules.timefix.infrastructure.images import ExifToolShifter, FolderOfImages
from wildintel_uploader.modules.timefix.infrastructure.outside import ToleranceInUse, VisitsThroughTheirContract
from wildintel_uploader.modules.visits.application.use_cases import VisitsUseCases
from wildintel_uploader.modules.visits.domain.ports import VisitsService
from wildintel_uploader.modules.visits.infrastructure.adapters import AuditClock, CatalogOfTheVisits, CollectionFolders as VisitCollectionFolders, FieldlogInUse, SavedVisitReports, StoredStateHistory, UploadsOfTheUploaders
from wildintel_uploader.modules.visits.infrastructure.adapters import StoredVisits as VisitsKept
from wildintel_uploader.modules.visits.infrastructure.csv_file import CsvVisitFile
from wildintel_uploader.modules.visits.infrastructure.kept_visits import KeptVisits
from wildintel_uploader.entrypoints import wiring as w   # the other factories, asked when called


def build_sources(settings: SettingsService | None = None) -> SourcesService:
    """The sources of the visits: Epicollect5 through pyepicollect, the settings through their module."""
    return SourcesUseCases(PyEpicollect5(), SettingsOfTheSources(settings or w.build_settings()), visit_sources.SOURCES,
                           form_columns=form_columns, form_error=form_error)


def build_visits(collections_dir: Path | None = None, settings: SettingsService | None = None) -> VisitsService:
    """The visits of the research projects of a collections folder — the one of the settings by default —, kept with the records of their research projects."""
    root = collections_dir or w.catalog_collections_dir()
    settings = settings or w.build_settings()
    catalog = lambda: w.build_catalog(root, settings)   # noqa: E731 — the catalog of that folder, through its contract
    return VisitsUseCases(VisitsKept(KeptVisits(root, catalog)), CatalogOfTheVisits(catalog),
                          deployments=VisitCollectionFolders(root, lambda: w.build_deployments().layout()), file=CsvVisitFile(),
                          sources=build_sources(settings), uploads=UploadsOfTheUploaders(w.build_uploaders(root)), reports=SavedVisitReports(w.build_reports()), history=StoredStateHistory(),
                          settings=FieldlogInUse(w.section("FIELDLOG")), clock=AuditClock())


def build_timefix() -> TimeFixService:
    """The fixes of the dates of the images: the visits of the collections folder of the settings, the images on disk and their dates as
    modules.fileinfo reads them, ExifTool to shift them, the fixes written down beside them."""
    files = w.file_info()
    return TimeFixUseCases(VisitsThroughTheirContract(lambda: build_visits()), FolderOfImages(), files, ExifToolShifter(files.exiftool_path),
                           CorrectionsFile(), ToleranceInUse(w.section("POSTVALIDATION")))


class SourcesProvider(Provider):
    """The sources of the visits."""

    @provide(scope=Scope.REQUEST)
    def service(self, settings: SettingsService) -> SourcesService:
        return build_sources(settings)

    # each part of the contract, for whoever needs only that one: the same service of the request
    visits = alias(source=SourcesService, provides=SourcesVisits)
    deployments = alias(source=SourcesService, provides=SourcesDeployments)
    project = alias(source=SourcesService, provides=SourcesProject)


class VisitsProvider(Provider):
    """The visits, in the collections folder the settings say."""

    @provide(scope=Scope.REQUEST)
    def service(self, settings: SettingsService) -> VisitsService:
        return build_visits(w.catalog_collections_dir(), settings)


class TimeFixProvider(Provider):
    @provide(scope=Scope.APP)
    def service(self) -> TimeFixService:
        return build_timefix()
