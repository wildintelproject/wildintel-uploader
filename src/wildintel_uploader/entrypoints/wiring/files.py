"""What is known of the files of the images, and what looks at them: the reports, the checks of the images and of a deployment, the preprocessing."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from dishka import Provider, Scope, provide

from wildintel_uploader.entrypoints import config
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
from wildintel_uploader.modules.postvalidation.domain import checks as deployment_validators
from wildintel_uploader.modules.postvalidation.infrastructure.adapters import CatalogCameras, LevelsInUse, RevisionsOfTheDeployments, SavedPostvalidationReports
from wildintel_uploader.modules.preprocessing.application.use_cases import PreprocessingUseCases
from wildintel_uploader.modules.preprocessing.domain.ports import PreprocessingService
from wildintel_uploader.modules.preprocessing.infrastructure import steps as preprocessing_steps
from wildintel_uploader.modules.preprocessing.infrastructure.folders import CollectionFolders, SavedReports
from wildintel_uploader.modules.prevalidation.application.use_cases import PrevalidationUseCases
from wildintel_uploader.modules.prevalidation.domain.ports import PrevalidationService
from wildintel_uploader.modules.prevalidation.domain import checks as image_validators
from wildintel_uploader.modules.prevalidation.infrastructure.adapters import PreprocessedImages, SavedValidationReports, ValidationInUse
from wildintel_uploader.modules.reports.application.use_cases import ReportsUseCases
from wildintel_uploader.modules.reports.domain.ports import ReportsService
from wildintel_uploader.modules.reports.infrastructure.report_files import ImagesOnDisk, ReportFiles
from wildintel_uploader.shared import parallel
from wildintel_uploader.entrypoints import wiring as w   # the other factories, asked when called


@lru_cache(maxsize=1)
def file_info() -> FileInfoService:
    """What is known of the files of the images: one for the whole process, on purpose, so that one reading of ExifTool runs at a time — the one
    that asks meanwhile waits for it, and finds what it read. ExifTool reads, Pillow only without it; remembered in memory and in the cache folder.

    It is the one the container gives too (FileInfoService, at the scope of the app): built once here, whoever asks. A test that needs a new one
    asks for it with `file_info.cache_clear()`."""
    return FileInfoUseCases(reader=ExifToolReader(), fallback=PillowReader(), decoder=PillowDecoder(), hasher=FileHasher(), stamps=OsStamps(),
                            memory=ProcessMemory(), store=SqliteStore())


def build_reports(reports_dir: Path | None = None) -> ReportsService:
    """The reports, as files in the reports folder — the settings' by default —, the failed images dated as modules.fileinfo reads them: what
    the other modules keep the reports of what they did through."""
    return ReportsUseCases(ReportFiles(lambda: reports_dir or config.reports_dir()), ImagesOnDisk(), file_info())


def build_prevalidation(info: FileInfoService | None = None) -> PrevalidationService:
    """The prevalidation: the validators of the images over what is known of the files, the images gone through in parallel."""
    return PrevalidationUseCases(info or file_info(), parallel.pmap, image_validators.VALIDATORS, imported=PreprocessedImages(w.build_deployments), settings=ValidationInUse(w.section("VALIDATION")),
                                 reports=SavedValidationReports(build_reports()))


def build_postvalidation(info: FileInfoService | None = None) -> PostvalidationService:
    """The postvalidation: the validators of a deployment over its images and what is known of them."""
    return PostvalidationUseCases(info or file_info(), parallel.pmap, deployment_validators.VALIDATORS, cameras=CatalogCameras(lambda: w.build_catalog(w.catalog_collections_dir(), w.build_settings())), levels=LevelsInUse(w.section("VALIDATION")),
                                  reports=SavedPostvalidationReports(build_reports()),
                                  revisions=RevisionsOfTheDeployments(w.build_deployments))


def build_preprocessing(info: FileInfoService | None = None) -> PreprocessingService:
    """The preprocessing: its steps over what is known of the files, in the collections folder as the rest of the app keeps it, with as many
    images at once as the settings say."""
    return PreprocessingUseCases(info or file_info(), CollectionFolders(lambda: w.build_deployments().layout()), SavedReports(build_reports()), image_steps=preprocessing_steps.IMAGE_STEPS,
                                 folder_steps=preprocessing_steps.FOLDER_STEPS, workers=config.workers, exiftool=lambda: exiftool_adapter.exiftool_path())


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


class ReportsProvider(Provider):
    @provide(scope=Scope.APP)
    def service(self) -> ReportsService:
        return build_reports()
